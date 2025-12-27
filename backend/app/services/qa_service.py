"""QA Service - Combines KG, Vector Search and LLM for Question Answering"""

import time
import uuid
import re
import asyncio
import json
from typing import List, Dict, Any, Optional, Tuple, AsyncGenerator
from loguru import logger

from app.core.config import settings
from app.models.query import (
    QueryRequest,
    QueryResponse,
    Evidence,
    KGPath,
    SourceType,
    AnswerSource
)
from app.services.kg_service import kg_service
from app.services.vector_service import vector_service
from app.services.memory_service import memory_service


class QAService:
    """Main service for medical question answering"""

    # 并发控制：限制同时处理的请求数
    MAX_CONCURRENT_REQUESTS = 5
    # LLM 调用超时时间（秒）
    LLM_TIMEOUT = 60

    # 常见同义词或口语化词映射到知识图谱中的规范名称
    SYNONYMS = {
        "小儿麻痹症": "脊髓灰质炎",
        "小儿麻痹": "脊髓灰质炎",
        "儿麻痹": "脊髓灰质炎",
        "普通流感": "流感",
        "流感": "流行性感冒",
        "感冒": "上呼吸道感染",
    }

    def __init__(self):
        self.openai_client = None
        self.gemini_model = None
        self.siliconflow_client = None
        self._llm_provider = "mock"  # "openai", "gemini", "siliconflow", or "mock"
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def initialize(self):
        """Initialize LLM client based on configuration"""
        # 初始化并发控制信号量
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

        provider = settings.llm_provider.lower()

        # Try SiliconFlow (DeepSeek) first if configured
        if provider == "siliconflow" and settings.siliconflow_api_key:
            try:
                from openai import AsyncOpenAI
                self.siliconflow_client = AsyncOpenAI(
                    api_key=settings.siliconflow_api_key,
                    base_url=settings.siliconflow_base_url
                )
                self._llm_provider = "siliconflow"
                logger.info(
                    f"SiliconFlow client initialized (model: {settings.siliconflow_model})")
                return
            except Exception as e:
                logger.warning(f"Failed to initialize SiliconFlow: {e}")

        # Try Gemini if configured
        if provider == "gemini" and settings.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.gemini_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                self._llm_provider = "gemini"
                logger.info("Gemini client initialized")
                return
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {e}")

        # Try OpenAI if configured
        if provider == "openai" and settings.openai_api_key and settings.openai_api_key.startswith("sk-"):
            try:
                from openai import AsyncOpenAI
                self.openai_client = AsyncOpenAI(
                    api_key=settings.openai_api_key)
                self._llm_provider = "openai"
                logger.info("OpenAI client initialized")
                return
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI: {e}")

        # Fallback to mock
        logger.info("No valid LLM API key provided. Using mock LLM responses.")
        self._llm_provider = "mock"

    async def _extract_entities_from_kg(self, query: str, history: list = None) -> List[str]:
        """从知识图谱中提取实体（更准确），并结合会话历史做核心指代消解。

        逻辑：
        1. 先用静态词表提取当前 query 的实体
        2. 如果连接 KG，则对当前 query 中的候选短词做 KG 模糊搜索
        3. 如果未能提取到实体，尝试从历史消息中回溯查找实体（处理代词/省略）
        4. 最后再把历史与 query 合并再次做一次提取（保障覆盖）
        """
        found_entities: List[str] = []

        # 1) 当前 query 的静态规则提取
        basic_entities = self._extract_entities(query)
        found_entities.extend(basic_entities)

        # 1b) 同义词/口语化匹配：优先把常见口语映射到规范疾病名
        for colloquial, canonical in self.SYNONYMS.items():
            if colloquial in query and canonical not in found_entities:
                found_entities.append(canonical)
                logger.debug(
                    f"Mapped colloquial '{colloquial}' to canonical '{canonical}' for query '{query}'")

        # 2) KG 增强：当前 query 中候选词的 KG 模糊/全文检索
        if kg_service.is_connected:
            import re
            potential_terms = re.findall(r'[\u4e00-\u9fa5]{2,6}', query)

            for term in potential_terms:
                if term in found_entities:
                    continue
                diseases = await kg_service.search_disease(term, limit=1)
                if diseases:
                    found_entities.append(diseases[0])
                    continue
                symptoms = await kg_service.search_symptom(term, limit=1)
                if symptoms:
                    found_entities.append(symptoms[0])

        # 3) 如果当前 query 没有提取到实体，尝试从历史回溯搜索（解决代词/省略问题）
        if (not found_entities) and history:
            import re
            # 优先从最近的用户消息中寻找可能的实体
            for msg in reversed(history[-6:]):
                # 只看用户发言优先
                if msg.role != 'user':
                    continue
                terms = re.findall(r'[\u4e00-\u9fa5]{2,12}', msg.content)
                for term in terms:
                    if term in found_entities:
                        continue
                    diseases = await kg_service.search_disease(term, limit=1)
                    if diseases:
                        found_entities.append(diseases[0])
                        break
                    symptoms = await kg_service.search_symptom(term, limit=1)
                    if symptoms:
                        found_entities.append(symptoms[0])
                        break
                if found_entities:
                    break

        # 3b) 如果仍未提取到实体，尝试更激进的直接从当前 query 做疾病检索（处理像“XX 是啥/是什么”的情况）
        if (not found_entities):
            import re
            # 清理常见问句后缀
            cleaned = re.sub(
                r'(是什么|是啥|啥是|是啥意思|是什么意思|是什么病|怎么回事|有哪些症状|症状|怎么办)$', '', query.strip())
            cleaned = cleaned.strip()

            # 先尝试用整个清理后的 query 去做疾病搜索
            if cleaned:
                diseases = await kg_service.search_disease(cleaned, limit=3)
                if diseases:
                    found_entities.extend(diseases)

            # 如果还是没有结果，做一个简易的 n-gram 扫描（长到短），尽量找到更具体的疾病名
            if not found_entities:
                text = re.findall(r'[\u4e00-\u9fa5]+', query)
                text = ''.join(text)  # 只保留中文字符
                for length in range(6, 1, -1):
                    for i in range(0, max(0, len(text) - length + 1)):
                        sub = text[i:i+length]
                        if sub in found_entities:
                            continue
                        diseases = await kg_service.search_disease(sub, limit=1)
                        if diseases:
                            found_entities.append(diseases[0])
                            break
                    if found_entities:
                        break

            # 记录发现以便调试
            if found_entities:
                logger.debug(
                    f"Fallback disease match from query '{query}': {found_entities}")

        # 4) 最后一步：把历史文本与当前 query 合并再做一次静态 + KG 检索（补偿性）
        if history and kg_service.is_connected:
            combined_text = ' '.join(
                [m.content for m in history[-6:]]) + ' ' + query
            more_entities = self._extract_entities(combined_text)
            import re
            potential_terms = re.findall(
                r'[\u4e00-\u9fa5]{2,6}', combined_text)

            for term in potential_terms:
                if term in found_entities:
                    continue
                diseases = await kg_service.search_disease(term, limit=1)
                if diseases:
                    found_entities.append(diseases[0])
                    continue
                symptoms = await kg_service.search_symptom(term, limit=1)
                if symptoms:
                    found_entities.append(symptoms[0])

            for ent in more_entities:
                if ent not in found_entities:
                    found_entities.append(ent)

        # preserve order, remove duplicates
        return list(dict.fromkeys(found_entities))

    def _extract_entities(self, query: str) -> List[str]:
        """Extract medical entities from query using simple pattern matching"""
        # Common medical terms to look for
        medical_terms = [
            "头痛", "偏头痛", "紧张性头痛", "发热", "发烧", "感冒", "流感",
            "咳嗽", "恶心", "呕吐", "腹痛", "腹泻", "便秘", "胸痛", "心悸",
            "高血压", "糖尿病", "哮喘", "过敏", "皮疹", "失眠", "焦虑", "抑郁",
            "布洛芬", "对乙酰氨基酚", "阿司匹林", "抗生素", "维生素",
            "脑膜炎", "脑卒中", "中风", "癫痫", "帕金森",
            "畏光", "颈部僵硬", "意识", "视力", "乏力", "疲劳",
            "肺炎", "支气管炎", "胃炎", "肠炎", "肝炎", "肾炎",
            "冠心病", "心肌梗死", "心绞痛", "心律失常",
            "骨折", "关节炎", "腰痛", "颈椎病", "肩周炎",
            "湿疹", "荨麻疹", "痤疮", "银屑病",
            "贫血", "白血病", "淋巴瘤"
        ]

        found_entities = []

        for term in medical_terms:
            if term in query:
                found_entities.append(term)

        return found_entities

    async def _extract_entities_from_query_only(self, query: str) -> List[str]:
        """Extract entities using only the current query (no history) with KG enhancement.

        This ensures evidence retrieval is scoped to the current user question, avoiding
        pulling in documents that were relevant only to earlier turns in the conversation.
        """
        found_entities: List[str] = []

        # Basic extraction from current query
        basic_entities = self._extract_entities(query)
        found_entities.extend(basic_entities)

        # KG-enhanced search using current query terms (no history)
        if kg_service.is_connected:
            import re
            potential_terms = re.findall(r'[\u4e00-\u9fa5]{2,6}', query)

            for term in potential_terms:
                if term in found_entities:
                    continue
                diseases = await kg_service.search_disease(term, limit=1)
                if diseases:
                    found_entities.append(diseases[0])
                    continue
                symptoms = await kg_service.search_symptom(term, limit=1)
                if symptoms:
                    found_entities.append(symptoms[0])

        # preserve order, remove duplicates
        return list(dict.fromkeys(found_entities))

    def _build_history_context(self, history: list = None) -> str:
        """构建对话历史上下文"""
        if not history or len(history) == 0:
            return ""

        history_context = "\n**对话历史**：\n"
        for msg in history[-6:]:  # 只保留最近6轮对话，避免上下文过长
            role_name = "用户" if msg.role == "user" else "助手"
            history_context += f"{role_name}：{msg.content}\n"
        history_context += "\n"
        return history_context

    def _build_llm_prompt(
        self,
        query: str,
        kg_context: str,
        evidence_context: str,
        history: list = None
    ) -> str:
        """Build the prompt for LLM with grounding instructions (有知识图谱数据时使用)"""
        history_context = self._build_history_context(history)

        return f"""你是一个专业的医疗信息助手。请根据提供的医疗知识图谱信息回答用户的问题。

**重要规则**：
1. 优先使用知识图谱中提供的医学信息来回答问题
2. 回答要准确、专业，但表达要通俗易懂
3. 如果知识图谱中有相关信息，请一定据此回答；如果没有，请说明"暂无相关信息"，并给出合理的建议。
4. 始终提醒用户本系统仅供参考，不能替代医生诊断
5. 对于危险信号（如剧烈头痛、高热、意识改变、胸痛），要强调立即就医
6. 如果有对话历史，请结合上下文理解用户的问题（如代词指代、省略的主语等）
7. 一些基本信息你是可以回复的，比如日期等。

**医疗知识图谱信息**：
{kg_context}
{history_context}
**当前用户问题**：
{query}

如果用户提问的是医学相关的问题，请提供结构化的回答，包括：
1. 简要回答（概括主要信息）
2. 详细说明（分点列出症状/治疗/预防等相关信息）
3. 就医建议（何时需要就医，看什么科室）
4. 注意事项（饮食、用药等）
否则不用提供结构化回答，简要回答即可。

回答："""

    def _build_llm_prompt_without_kg(
        self,
        query: str,
        history: list = None
    ) -> str:
        """当知识图谱无数据时，构建纯 LLM 的 prompt"""
        history_context = self._build_history_context(history)

        return f"""你是一个专业的医疗信息助手。

**重要说明**：
当前医疗知识图谱中未找到与用户问题直接相关的信息，请根据你的医学专业知识提供参考建议。

**回答要求**：
1. 回答要准确、专业，但表达要通俗易懂
2. 始终强调本回答仅供参考，不能替代专业医生的诊断和治疗
3. 对于危险信号（如剧烈头痛、高热不退、意识改变、胸痛、呼吸困难等），要强调立即就医
4. 不要在回答中提及"知识图谱"，直接给出专业建议即可
5. 如果有对话历史，请结合上下文理解用户的问题
{history_context}
**用户问题**：
{query}

如果用户提问的是医学相关的问题，请提供结构化的回答，包括：
1. 简要回答（概括主要信息）
2. 详细说明（分点列出症状/治疗/预防等相关信息）
3. 就医建议（何时需要就医，看什么科室）
4. 注意事项（饮食、用药等）
否则不用提供结构化回答，简要回答即可。

回答："""

    async def _generate_kg_based_response(
        self,
        query: str,
        entities: List[str],
        kg_context: str
    ) -> str:
        """基于知识图谱生成回答"""
        if not kg_context:
            return await self._generate_fallback_response(query, entities)

        # 构建基于知识图谱的回答
        response = f"## 关于您的问题\n\n根据医疗知识库的信息，为您提供以下参考：\n\n{kg_context}\n"
        response += "\n---\n📚 **提示**：本回答基于医疗知识图谱生成，未使用AI大模型。\n"
        response += "⚠️ **重要提示**：以上信息仅供参考，不能替代专业医生的诊断和治疗建议。如有身体不适，请及时就医。"

        return response

    async def _generate_fallback_response(self, query: str, entities: List[str]) -> str:
        """当没有知识图谱数据时的备用回答"""
        return f"""## 关于您的问题

感谢您的咨询。

目前知识库中暂无关于"{', '.join(entities) if entities else '您所询问内容'}"的详细信息。

**建议**：
1. 尝试使用更具体的医学术语进行查询
2. 如有身体不适，请及时前往医院就诊
3. 可以咨询专业医生获取准确的诊断和治疗建议

---
📚 **提示**：本回答基于医疗知识图谱生成，未使用AI大模型。
⚠️ **重要提示**：本系统仅供医疗信息参考，不能替代专业医生的诊断和治疗建议。"""

    def _generate_mock_response(
        self,
        query: str,
        entities: List[str],
        evidence: List[Evidence],
        kg_paths: List[KGPath],
        kg_context: str = ""
    ) -> str:
        """Generate a mock response based on retrieved evidence"""
        # 备用方案提示信息
        fallback_notice = "\n\n---\n📚 **提示**：本回答基于医疗知识图谱生成，未使用AI大模型。\n"

        # 如果有知识图谱上下文，优先使用
        if kg_context:
            response = f"## 关于您的问题\n\n根据医疗知识库的信息，为您提供以下参考：\n\n{kg_context}\n"
            response += fallback_notice
            response += "⚠️ **重要提示**：以上信息仅供参考，不能替代专业医生的诊断和治疗建议。如有身体不适，请及时就医。"
            return response

        # Check for headache-related queries
        if any(term in query for term in ["头痛", "头疼", "偏头痛"]):
            return self._generate_headache_response(query, evidence, kg_paths) + fallback_notice

        # Check for fever-related queries
        if any(term in query for term in ["发热", "发烧", "体温"]):
            return self._generate_fever_response(query, evidence) + fallback_notice

        # Check for drug-related queries
        if any(term in query for term in ["药", "用药", "吃什么药", "布洛芬", "对乙酰氨基酚"]):
            return self._generate_drug_response(query, evidence) + fallback_notice

        # Check for diabetes
        if any(term in query for term in ["糖尿病", "血糖"]):
            return self._generate_diabetes_response(query, evidence) + fallback_notice

        # Check for hypertension
        if any(term in query for term in ["高血压", "血压"]):
            return self._generate_hypertension_response(query, evidence) + fallback_notice

        # Default response
        return self._generate_default_response(query, evidence) + fallback_notice

    def _generate_headache_response(
        self,
        query: str,
        evidence: List[Evidence],
        kg_paths: List[KGPath]
    ) -> str:
        """Generate response for headache-related queries"""
        response = """## 头痛的可能原因分析

根据您描述的症状，头痛可能由以下几种常见原因引起：

### 常见原因

1. **偏头痛** [来源: 中华神经科杂志, PMID:34567890]
   - 表现为反复发作的中重度搏动性头痛
   - 常伴有恶心、呕吐、畏光和畏声
   - 发作通常持续4-72小时

2. **紧张性头痛** [来源: Headache, PMID:34567891]
   - 最常见的头痛类型，终生患病率达78%
   - 表现为双侧压迫性或紧箍样头痛
   - 程度轻至中度，不因日常活动加重

3. **上呼吸道感染（感冒/流感）**
   - 尤其在伴有发热、咳嗽、流涕时需考虑
   - 头痛通常为全头部钝痛

### ⚠️ 需要立即就医的危险信号 [来源: NICE临床指南]

如出现以下情况，请**立即**前往医院就诊：
- **雷击样头痛**：数秒内达到高峰的剧烈头痛
- **伴发热和颈部僵硬**：可能提示脑膜炎
- **意识改变或神经功能缺损**
- **头痛进行性加重**
- **50岁以后新发头痛**
- **伴视力改变或眼痛**

### 建议

1. 保持充足休息，避免过度劳累
2. 可考虑对症服用对乙酰氨基酚（1000mg）或布洛芬（400-600mg）缓解症状
3. 如头痛持续超过3天或频繁发作，建议就医进一步评估
4. 记录头痛日记（发作时间、持续时间、诱因、伴随症状）有助于诊断"""

        return response

    def _generate_fever_response(self, query: str, evidence: List[Evidence]) -> str:
        """Generate response for fever-related queries"""
        return """## 发热的评估与建议

### 发热定义
发热定义为核心体温≥38°C（腋温≥37.3°C可视为低热）。[来源: 中华内科杂志, PMID:34567893]

### 常见原因
1. **感染性疾病**（最常见）
   - 上呼吸道感染、流感
   - 肺炎、泌尿道感染等

2. **非感染性原因**
   - 自身免疫疾病
   - 药物热

### ⚠️ 需要就医的情况
- 体温≥39°C持续24小时以上
- 伴有剧烈头痛和颈部僵硬（警惕脑膜炎）
- 伴有意识改变
- 伴有皮疹
- 儿童、老年人或免疫力低下者

### 对症处理建议
1. 多饮水，保持休息
2. 可服用对乙酰氨基酚或布洛芬退热
3. 物理降温（温水擦浴）
4. 如持续不退或伴有其他症状，请及时就医"""

    def _generate_drug_response(self, query: str, evidence: List[Evidence]) -> str:
        """Generate response for drug-related queries"""
        return """## 药物信息

### 常用止痛退热药物 [来源: DrugBank, Cochrane]

1. **对乙酰氨基酚（扑热息痛）**
   - 用法：成人每次500-1000mg，每4-6小时一次
   - 每日最大剂量：4000mg
   - 适用于轻至中度疼痛和退热
   - 注意：避免过量，有肝损害风险

2. **布洛芬** [来源: DrugBank DB01050]
   - 用法：成人每次200-400mg，每4-6小时一次
   - 每日最大剂量：1200mg（非处方）
   - 同时具有止痛、退热、抗炎作用
   - 禁忌：活动性消化道溃疡、严重心衰

### ⚠️ 用药注意事项
- 每月使用止痛药不宜超过10天，以防药物过度使用性头痛
- 有胃病史者慎用NSAIDs类药物
- 肝肾功能不全者请遵医嘱调整剂量
- 如需长期用药，请咨询医生"""

    def _generate_diabetes_response(self, query: str, evidence: List[Evidence]) -> str:
        """Generate response for diabetes-related queries"""
        return """## 糖尿病相关信息 [来源: 中华糖尿病杂志 2024年指南]

### 2型糖尿病管理要点

**控制目标**：
- HbA1c < 7%（可根据个体情况调整）
- 空腹血糖：4.4-7.0 mmol/L
- 餐后2小时血糖：< 10.0 mmol/L

**一线用药**：
- 二甲双胍是2型糖尿病首选药物
- 无禁忌症患者应从诊断时开始使用

**生活方式干预**：
1. 饮食控制：控制总热量，均衡营养
2. 规律运动：每周至少150分钟中等强度运动
3. 戒烟限酒
4. 控制体重

**定期监测**：
- 血糖监测
- 每3-6个月检测HbA1c
- 每年眼底检查
- 每年肾功能检查
- 定期足部检查

⚠️ 糖尿病管理需要个体化方案，请遵医嘱治疗。"""

    def _generate_hypertension_response(self, query: str, evidence: List[Evidence]) -> str:
        """Generate response for hypertension-related queries"""
        return """## 高血压相关信息 [来源: 中国高血压防治指南 2023]

### 诊断标准
非同日3次血压测量≥140/90mmHg即可诊断高血压。

### 治疗目标
- 一般患者：< 140/90 mmHg
- 高危患者：< 130/80 mmHg

### 一线降压药物
1. ACEI/ARB（普利类/沙坦类）
2. CCB（地平类）
3. 利尿剂
4. β受体阻滞剂

### 生活方式改变
1. **限盐**：每日摄盐<6g
2. **减重**：BMI控制在24以下
3. **戒烟**：完全戒烟
4. **限酒**：男性<25g/天，女性<15g/天
5. **运动**：每周5-7天，每次30分钟有氧运动

### ⚠️ 注意事项
- 高血压需要长期管理，不可自行停药
- 血压波动大或控制不佳请及时就医
- 定期监测血压并记录"""

    def _generate_default_response(self, query: str, evidence: List[Evidence]) -> str:
        """Generate a default response when no specific pattern matches"""
        evidence_summary = ""
        if evidence:
            evidence_summary = "\n\n### 相关参考资料\n"
            for i, ev in enumerate(evidence[:3], 1):
                evidence_summary += f"{i}. {ev.section or '医学文献'} [来源: {ev.source}]\n"

        return f"""## 关于您的问题

感谢您的咨询。根据您的问题，我检索了相关的医学资料。

由于问题的具体性，建议您：

1. **详细描述症状**：包括持续时间、严重程度、伴随症状等
2. **咨询专业医生**：获取针对性的诊断和治疗建议
3. **不要自行用药**：特别是处方药物

{evidence_summary}

⚠️ 本系统仅供信息参考，不能替代专业医生的诊断和治疗建议。如有不适，请及时就医。"""

    async def process_query(self, request: QueryRequest) -> QueryResponse:
        """Process a medical question and return structured answer with evidence"""
        # 使用信号量控制并发，防止同时处理太多请求
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

        async with self._semaphore:
            return await self._process_query_internal(request)

    async def _process_query_internal(self, request: QueryRequest) -> QueryResponse:
        """Internal method to process a query with concurrency control"""
        start_time = time.time()
        query_id = f"q_{uuid.uuid4().hex[:12]}"

        logger.info(f"Processing query [{query_id}]: {request.query[:50]}...")

        # Step 1: Extract entities from query (使用知识图谱增强)，并结合历史做指代消解
        entities = await self._extract_entities_from_kg(request.query, request.history)
        logger.debug(f"Extracted entities: {entities}")

        # Step 2: Retrieve from Knowledge Graph
        kg_paths = []
        if request.include_kg_paths and entities:
            kg_paths = await kg_service.find_paths_for_query(entities)
            logger.debug(f"Found {len(kg_paths)} KG paths")

        # Step 3: Retrieve from Vector Store (documents/literature)
        evidence = []
        if request.include_evidence:
            # Use entities extracted from the current query only to avoid pulling evidence from prior turns
            current_entities = await self._extract_entities_from_query_only(request.query)
            evidence = await vector_service.search_documents(
                request.query,
                keywords=current_entities,
                limit=request.max_answers + 2
            )
            logger.debug(
                f"Extracted current-only entities for evidence: {current_entities}")
            logger.debug(f"Found {len(evidence)} evidence documents")

        # Step 4: Search user memory (semantic-like) and Build context for LLM (使用知识图谱增强)
        kg_context = ""

        # 首先检索用户记忆（如果有），把高相关记忆作为补充上下文
        memory_results = []
        try:
            if request.user_id:
                memory_results = await memory_service.search_memory(request.query, user_id=request.user_id, top_k=5)
                if memory_results:
                    mem_text = "用户历史记忆：\n"
                    for m in memory_results:
                        mem_text += f"- ({round(m.get('score',0),2)}) {m.get('content')}\n"
                    kg_context += mem_text + "\n"
        except Exception as e:
            logger.debug(f"Memory search failed: {e}")

        if entities and kg_service.is_connected:
            # 从知识图谱获取详细上下文
            kg_context += await kg_service.get_kg_context_for_query(entities)

        if not kg_context and kg_paths:
            # 备用：从路径构建上下文
            kg_context = kg_context or "相关医学知识：\n"
            for path in kg_paths[:3]:
                for node in path.nodes:
                    kg_context += f"- {node.type}: {node.label}"
                    if node.properties.get("description"):
                        kg_context += f" - {node.properties['description']}"
                    kg_context += "\n"

        evidence_context = ""
        if evidence:
            evidence_context = "医学文献证据：\n"
            for ev in evidence[:5]:
                evidence_context += f"- [{ev.source}] {ev.snippet}\n"

        # 将记忆检索结果也加入证据上下文（如果有）
        if memory_results:
            evidence_context += "\n检索到的相关记忆：\n"
            for m in memory_results:
                evidence_context += f"- {m.get('content')}\n"

        # Step 5: Generate answer
        # 判断知识图谱是否有数据
        kg_available = bool(kg_context or kg_paths)

        # 构建消息历史列表（用于支持上下文的 LLM 调用）
        history_messages = []
        if request.history:
            for msg in request.history[-6:]:  # 限制历史长度
                history_messages.append(
                    {"role": msg.role, "content": msg.content})

        # 获取当前使用的模型名称（用于标注）
        model_name_map = {
            "mock": "模板回复",
            "gemini": "Gemini",
            "openai": "GPT-4",
            "siliconflow": settings.siliconflow_model
        }
        current_model_name = model_name_map.get(self._llm_provider, "AI")

        # 无知识图谱数据时的来源标注
        no_kg_notice = f"""

---
🤖 **来源说明**：知识图谱中未找到相关信息，本回答由 AI 大模型（{current_model_name}）基于通用医学知识生成。
⚠️ **重要提示**：AI 生成内容仅供参考，可能存在误差，请以专业医生诊断为准。如有身体不适，请及时就医。"""

        if self._llm_provider == "mock":
            # Mock 模式：无知识图谱时返回提示，有知识图谱时返回模板
            if kg_available:
                answer = self._generate_mock_response(
                    request.query, entities, evidence, kg_paths, kg_context)
            else:
                answer = await self._generate_fallback_response(request.query, entities)
        elif self._llm_provider == "siliconflow":
            # 根据知识图谱是否有数据选择不同的 prompt
            if kg_available:
                prompt = self._build_llm_prompt(
                    request.query, kg_context, evidence_context, request.history)
                system_content = "你是一个专业、严谨的医疗信息助手。请根据提供的医疗知识图谱信息，为用户提供准确、专业的医疗健康建议。如果有对话历史，请结合上下文理解用户意图。"
            else:
                prompt = self._build_llm_prompt_without_kg(
                    request.query, request.history)
                system_content = "你是一个专业、严谨的医疗信息助手。请根据你的医学专业知识，为用户提供准确、专业的医疗健康建议。如果有对话历史，请结合上下文理解用户意图。"

            try:
                # 构建完整的消息列表
                messages = [{"role": "system", "content": system_content}]
                messages.extend(history_messages)
                messages.append({"role": "user", "content": prompt})

                # 添加超时控制
                response = await asyncio.wait_for(
                    self.siliconflow_client.chat.completions.create(
                        model=settings.siliconflow_model,
                        messages=messages,
                        temperature=0.3,
                        max_tokens=2000
                    ),
                    timeout=self.LLM_TIMEOUT
                )
                answer = response.choices[0].message.content

                # 如果无知识图谱数据，追加来源标注
                if not kg_available:
                    answer += no_kg_notice

            except asyncio.TimeoutError:
                logger.warning(
                    f"SiliconFlow call timed out after {self.LLM_TIMEOUT}s, using fallback")
                answer = self._generate_mock_response(
                    request.query, entities, evidence, kg_paths, kg_context)
            except Exception as e:
                logger.error(f"SiliconFlow generation failed: {e}")
                answer = self._generate_mock_response(
                    request.query, entities, evidence, kg_paths, kg_context)
        elif self._llm_provider == "gemini":
            # 根据知识图谱是否有数据选择不同的 prompt
            if kg_available:
                prompt = self._build_llm_prompt(
                    request.query, kg_context, evidence_context, request.history)
                system_prefix = "你是一个专业、严谨的医疗信息助手。请根据提供的医疗知识图谱信息回答问题。"
            else:
                prompt = self._build_llm_prompt_without_kg(
                    request.query, request.history)
                system_prefix = "你是一个专业、严谨的医疗信息助手。请根据你的医学专业知识回答问题。"

            try:
                loop = asyncio.get_event_loop()
                response = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self.gemini_model.generate_content(
                            f"{system_prefix}\n\n{prompt}",
                            generation_config={
                                "temperature": 0.3,
                                "max_output_tokens": 2000,
                            }
                        )
                    ),
                    timeout=self.LLM_TIMEOUT
                )
                answer = response.text

                # 如果无知识图谱数据，追加来源标注
                if not kg_available:
                    answer += no_kg_notice

            except asyncio.TimeoutError:
                logger.warning(
                    f"Gemini call timed out after {self.LLM_TIMEOUT}s, using fallback")
                answer = self._generate_mock_response(
                    request.query, entities, evidence, kg_paths, kg_context)
            except Exception as e:
                logger.error(f"Gemini generation failed: {e}")
                answer = self._generate_mock_response(
                    request.query, entities, evidence, kg_paths, kg_context)
        else:  # openai
            # 根据知识图谱是否有数据选择不同的 prompt
            if kg_available:
                prompt = self._build_llm_prompt(
                    request.query, kg_context, evidence_context, request.history)
                system_content = "你是一个专业、严谨的医疗信息助手。请根据提供的医疗知识图谱信息回答问题。如果有对话历史，请结合上下文理解用户意图。"
            else:
                prompt = self._build_llm_prompt_without_kg(
                    request.query, request.history)
                system_content = "你是一个专业、严谨的医疗信息助手。请根据你的医学专业知识回答问题。如果有对话历史，请结合上下文理解用户意图。"

            try:
                messages = [{"role": "system", "content": system_content}]
                messages.extend(history_messages)
                messages.append({"role": "user", "content": prompt})

                response = await asyncio.wait_for(
                    self.openai_client.chat.completions.create(
                        model="gpt-4",
                        messages=messages,
                        temperature=0.3,
                        max_tokens=2000
                    ),
                    timeout=self.LLM_TIMEOUT
                )
                answer = response.choices[0].message.content

                # 如果无知识图谱数据，追加来源标注
                if not kg_available:
                    answer += no_kg_notice

            except asyncio.TimeoutError:
                logger.warning(
                    f"OpenAI call timed out after {self.LLM_TIMEOUT}s, using fallback")
                answer = self._generate_mock_response(
                    request.query, entities, evidence, kg_paths, kg_context)
            except Exception as e:
                logger.error(f"OpenAI generation failed: {e}")
                answer = self._generate_mock_response(
                    request.query, entities, evidence, kg_paths, kg_context)

        # Calculate processing time
        processing_time = int((time.time() - start_time) * 1000)

        # Calculate overall confidence
        confidence_scores = [ev.confidence for ev in evidence if ev.confidence]
        overall_confidence = sum(
            confidence_scores) / len(confidence_scores) if confidence_scores else 0.7

        # Build warnings
        warnings = []
        if not evidence:
            warnings.append("未找到直接相关的医学文献")
        if not kg_available:
            warnings.append("知识图谱中未找到相关信息")
        if not kg_service.is_connected:
            warnings.append("知识图谱服务未连接")

        # Determine answer source
        if self._llm_provider == "mock":
            if kg_available:
                answer_source = AnswerSource.KNOWLEDGE_GRAPH
            else:
                answer_source = AnswerSource.TEMPLATE
        else:
            if kg_available:
                answer_source = AnswerSource.MIXED  # 知识图谱 + LLM
            else:
                answer_source = AnswerSource.LLM_ONLY  # 纯 LLM 生成

        # Standard disclaimer
        disclaimer = "⚠️ 重要提示：本系统仅供医疗信息参考，不能替代专业医生的诊断和治疗建议。如有身体不适，请及时就医。紧急情况请拨打急救电话。"

        # If user_id present, store a short memory snippet (non-blocking)
        try:
            if request.user_id:
                mem_content = f"Q: {request.query}\nA: {answer[:1000]}"
                asyncio.create_task(memory_service.store_memory(
                    request.user_id, mem_content, {"query_id": query_id}))
        except Exception as e:
            logger.debug(f"Failed to store memory: {e}")

        return QueryResponse(
            query_id=query_id,
            answer=answer,
            answer_source=answer_source,
            evidence=evidence[:request.max_answers],
            kg_paths=kg_paths,
            confidence_score=round(overall_confidence, 2),
            warnings=warnings,
            disclaimer=disclaimer,
            processing_time_ms=processing_time,
            model_used={"mock": "mock-llm", "gemini": "gemini-1.5-flash", "openai": "gpt-4",
                        "siliconflow": settings.siliconflow_model}.get(self._llm_provider, "mock-llm")
        )

    async def process_query_stream(self, request: QueryRequest) -> AsyncGenerator[str, None]:
        """
        流式处理医疗问答查询，逐步返回LLM生成的内容

        Yields:
            SSE格式的字符串数据
        """
        # 使用信号量控制并发
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

        async with self._semaphore:
            async for chunk in self._process_query_stream_internal(request):
                yield chunk

    async def _process_query_stream_internal(self, request: QueryRequest) -> AsyncGenerator[str, None]:
        """流式处理查询的内部方法"""
        start_time = time.time()
        query_id = f"q_{uuid.uuid4().hex[:12]}"

        logger.info(
            f"Processing stream query [{query_id}]: {request.query[:50]}...")

        # 发送开始状态
        yield f"data: {json.dumps({'status': 'searching', 'message': '正在检索知识图谱...'}, ensure_ascii=False)}\n\n"

        # Step 1: Extract entities from query (结合历史进行消解)
        entities = await self._extract_entities_from_kg(request.query, request.history)
        logger.debug(f"Extracted entities: {entities}")

        # Step 2: Retrieve from Knowledge Graph
        kg_paths = []
        if request.include_kg_paths and entities:
            kg_paths = await kg_service.find_paths_for_query(entities)
            logger.debug(f"Found {len(kg_paths)} KG paths")

        # Step 3: Retrieve from Vector Store
        evidence = []
        if request.include_evidence:
            # Use entities extracted from the current query only to avoid pulling evidence from prior turns
            current_entities = await self._extract_entities_from_query_only(request.query)
            evidence = await vector_service.search_documents(
                request.query,
                keywords=current_entities,
                limit=request.max_answers + 2
            )
            logger.debug(
                f"Extracted current-only entities for evidence: {current_entities}")
            logger.debug(f"Found {len(evidence)} evidence documents")

        # 发送证据找到状态
        yield f"data: {json.dumps({'status': 'evidence_found', 'count': len(evidence)}, ensure_ascii=False)}\n\n"

        # Step 4: Build context for LLM
        kg_context = ""
        if entities and kg_service.is_connected:
            kg_context = await kg_service.get_kg_context_for_query(entities)

        if not kg_context and kg_paths:
            kg_context = "相关医学知识：\n"
            for path in kg_paths[:3]:
                for node in path.nodes:
                    kg_context += f"- {node.type}: {node.label}"
                    if node.properties.get("description"):
                        kg_context += f" - {node.properties['description']}"
                    kg_context += "\n"

        evidence_context = ""
        if evidence:
            evidence_context = "医学文献证据：\n"
            for ev in evidence[:5]:
                evidence_context += f"- [{ev.source}] {ev.snippet}\n"

        # 判断知识图谱是否有数据
        kg_available = bool(kg_context or kg_paths)

        # 构建消息历史列表
        history_messages = []
        if request.history:
            for msg in request.history[-6:]:
                history_messages.append(
                    {"role": msg.role, "content": msg.content})

        # 获取当前使用的模型名称
        model_name_map = {
            "mock": "模板回复",
            "gemini": "Gemini",
            "openai": "GPT-4",
            "siliconflow": settings.siliconflow_model
        }
        current_model_name = model_name_map.get(self._llm_provider, "AI")

        # 无知识图谱数据时的来源标注
        no_kg_notice = f"""

---
🤖 **来源说明**：知识图谱中未找到相关信息，本回答由 AI 大模型（{current_model_name}）基于通用医学知识生成。
⚠️ **重要提示**：AI 生成内容仅供参考，可能存在误差，请以专业医生诊断为准。如有身体不适，请及时就医。"""

        # 发送开始生成状态
        yield f"data: {json.dumps({'status': 'generating', 'message': '正在生成回答...'}, ensure_ascii=False)}\n\n"

        full_answer = ""

        if self._llm_provider == "mock":
            # Mock 模式：无法流式，直接返回完整回答
            if kg_available:
                answer = self._generate_mock_response(
                    request.query, entities, evidence, kg_paths, kg_context)
            else:
                answer = await self._generate_fallback_response(request.query, entities)

            # 模拟流式输出
            for char in answer:
                yield f"data: {json.dumps({'status': 'content', 'text': char}, ensure_ascii=False)}\n\n"
                full_answer += char
                await asyncio.sleep(0.01)  # 模拟打字效果

        elif self._llm_provider == "siliconflow":
            # SiliconFlow 流式输出
            if kg_available:
                prompt = self._build_llm_prompt(
                    request.query, kg_context, evidence_context, request.history)
                system_content = "你是一个专业、严谨的医疗信息助手。请根据提供的医疗知识图谱信息，为用户提供准确、专业的医疗健康建议。如果有对话历史，请结合上下文理解用户意图。"
            else:
                prompt = self._build_llm_prompt_without_kg(
                    request.query, request.history)
                system_content = "你是一个专业、严谨的医疗信息助手。请根据你的医学专业知识，为用户提供准确、专业的医疗健康建议。如果有对话历史，请结合上下文理解用户意图。"

            try:
                messages = [{"role": "system", "content": system_content}]
                messages.extend(history_messages)
                messages.append({"role": "user", "content": prompt})

                # 流式调用
                stream = await self.siliconflow_client.chat.completions.create(
                    model=settings.siliconflow_model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=2000,
                    stream=True
                )

                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_answer += content
                        yield f"data: {json.dumps({'status': 'content', 'text': content}, ensure_ascii=False)}\n\n"

                # 如果无知识图谱数据，追加来源标注
                if not kg_available:
                    full_answer += no_kg_notice
                    yield f"data: {json.dumps({'status': 'content', 'text': no_kg_notice}, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"SiliconFlow stream generation failed: {e}")
                answer = self._generate_mock_response(
                    request.query, entities, evidence, kg_paths, kg_context)
                yield f"data: {json.dumps({'status': 'content', 'text': answer}, ensure_ascii=False)}\n\n"
                full_answer = answer

        elif self._llm_provider == "gemini":
            # Gemini 流式输出
            if kg_available:
                prompt = self._build_llm_prompt(
                    request.query, kg_context, evidence_context, request.history)
                system_prefix = "你是一个专业、严谨的医疗信息助手。请根据提供的医疗知识图谱信息回答问题。"
            else:
                prompt = self._build_llm_prompt_without_kg(
                    request.query, request.history)
                system_prefix = "你是一个专业、严谨的医疗信息助手。请根据你的医学专业知识回答问题。"

            try:
                loop = asyncio.get_event_loop()
                # Gemini 流式调用
                response = await loop.run_in_executor(
                    None,
                    lambda: self.gemini_model.generate_content(
                        f"{system_prefix}\n\n{prompt}",
                        generation_config={
                            "temperature": 0.3,
                            "max_output_tokens": 2000,
                        },
                        stream=True
                    )
                )

                for chunk in response:
                    if chunk.text:
                        full_answer += chunk.text
                        yield f"data: {json.dumps({'status': 'content', 'text': chunk.text}, ensure_ascii=False)}\n\n"

                # 如果无知识图谱数据，追加来源标注
                if not kg_available:
                    full_answer += no_kg_notice
                    yield f"data: {json.dumps({'status': 'content', 'text': no_kg_notice}, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"Gemini stream generation failed: {e}")
                answer = self._generate_mock_response(
                    request.query, entities, evidence, kg_paths, kg_context)
                yield f"data: {json.dumps({'status': 'content', 'text': answer}, ensure_ascii=False)}\n\n"
                full_answer = answer

        else:  # openai
            # OpenAI 流式输出
            if kg_available:
                prompt = self._build_llm_prompt(
                    request.query, kg_context, evidence_context, request.history)
                system_content = "你是一个专业、严谨的医疗信息助手。请根据提供的医疗知识图谱信息回答问题。如果有对话历史，请结合上下文理解用户意图。"
            else:
                prompt = self._build_llm_prompt_without_kg(
                    request.query, request.history)
                system_content = "你是一个专业、严谨的医疗信息助手。请根据你的医学专业知识回答问题。如果有对话历史，请结合上下文理解用户意图。"

            try:
                messages = [{"role": "system", "content": system_content}]
                messages.extend(history_messages)
                messages.append({"role": "user", "content": prompt})

                # 流式调用
                stream = await self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=messages,
                    temperature=0.3,
                    max_tokens=2000,
                    stream=True
                )

                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_answer += content
                        yield f"data: {json.dumps({'status': 'content', 'text': content}, ensure_ascii=False)}\n\n"

                # 如果无知识图谱数据，追加来源标注
                if not kg_available:
                    full_answer += no_kg_notice
                    yield f"data: {json.dumps({'status': 'content', 'text': no_kg_notice}, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"OpenAI stream generation failed: {e}")
                answer = self._generate_mock_response(
                    request.query, entities, evidence, kg_paths, kg_context)
                yield f"data: {json.dumps({'status': 'content', 'text': answer}, ensure_ascii=False)}\n\n"
                full_answer = answer

        # Calculate processing time
        processing_time = int((time.time() - start_time) * 1000)

        # Calculate overall confidence
        confidence_scores = [ev.confidence for ev in evidence if ev.confidence]
        overall_confidence = sum(
            confidence_scores) / len(confidence_scores) if confidence_scores else 0.7

        # Build warnings
        warnings = []
        if not evidence:
            warnings.append("未找到直接相关的医学文献")
        if not kg_available:
            warnings.append("知识图谱中未找到相关信息")
        if not kg_service.is_connected:
            warnings.append("知识图谱服务未连接")

        # Determine answer source
        if self._llm_provider == "mock":
            if kg_available:
                answer_source = AnswerSource.KNOWLEDGE_GRAPH
            else:
                answer_source = AnswerSource.TEMPLATE
        else:
            if kg_available:
                answer_source = AnswerSource.MIXED
            else:
                answer_source = AnswerSource.LLM_ONLY

        # Standard disclaimer
        disclaimer = "⚠️ 重要提示：本系统仅供医疗信息参考，不能替代专业医生的诊断和治疗建议。如有身体不适，请及时就医。紧急情况请拨打急救电话。"

        # 构建完整响应
        final_response = QueryResponse(
            query_id=query_id,
            answer=full_answer,
            answer_source=answer_source,
            evidence=evidence[:request.max_answers],
            kg_paths=kg_paths,
            confidence_score=round(overall_confidence, 2),
            warnings=warnings,
            disclaimer=disclaimer,
            processing_time_ms=processing_time,
            model_used={"mock": "mock-llm", "gemini": "gemini-1.5-flash", "openai": "gpt-4",
                        "siliconflow": settings.siliconflow_model}.get(self._llm_provider, "mock-llm")
        )

        # Store memory (async) if user_id provided
        try:
            if request.user_id:
                mem_content = f"Q: {request.query}\nA: {full_answer[:1000]}"
                asyncio.create_task(memory_service.store_memory(
                    request.user_id, mem_content, {"query_id": query_id}))
        except Exception as e:
            logger.debug(f"Failed to store memory: {e}")

        # 发送完成状态和完整响应数据
        yield f"data: {json.dumps({'status': 'complete', 'response': json.loads(final_response.model_dump_json())}, ensure_ascii=False)}\n\n"


# Singleton instance
qa_service = QAService()
