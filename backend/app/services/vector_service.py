"""Vector Search Service - Document/Literature Retrieval"""

from typing import List, Dict, Any, Optional
from loguru import logger

from app.core.config import settings
from app.models.query import Evidence, SourceType


class VectorService:
    """Service for vector-based document retrieval"""
    
    def __init__(self):
        self.client = None
        self._is_connected = False
        self._mock_mode = True  # Use mock data for MVP
        
        # Mock medical literature database
        self._mock_documents: List[Dict[str, Any]] = []
        self._init_mock_documents()
    
    def _init_mock_documents(self):
        """Initialize mock medical literature for demonstration"""
        self._mock_documents = [
            # Headache related
            {
                "id": "doc_001",
                "title": "偏头痛的诊断与治疗进展",
                "content": "偏头痛是一种常见的原发性头痛，全球患病率约为12%。典型表现为反复发作的中重度搏动性头痛，常伴有恶心、呕吐、畏光和畏声。发作持续4-72小时。诊断主要依据临床表现，需排除继发性头痛。",
                "source": "中华神经科杂志",
                "source_type": "pubmed",
                "pmid": "34567890",
                "year": "2023",
                "keywords": ["偏头痛", "头痛", "诊断", "治疗"],
                "confidence": 0.95
            },
            {
                "id": "doc_002",
                "title": "紧张性头痛的流行病学与管理",
                "content": "紧张性头痛是最常见的头痛类型，终生患病率可达78%。表现为双侧压迫性或紧箍样头痛，程度轻至中度，不因日常活动加重。管理包括生活方式调整、放松训练和必要时的药物治疗。",
                "source": "Headache: The Journal of Head and Face Pain",
                "source_type": "pubmed",
                "pmid": "34567891",
                "year": "2023",
                "keywords": ["紧张性头痛", "头痛", "流行病学"],
                "confidence": 0.92
            },
            {
                "id": "doc_003",
                "title": "头痛的危险信号与紧急就医指征",
                "content": "以下情况需立即就医：1)雷击样头痛（数秒内达到高峰的剧烈头痛）；2)伴发热和颈部僵硬；3)伴意识改变或神经功能缺损；4)头痛进行性加重；5)50岁以后新发头痛；6)伴视力改变或眼痛。这些可能提示蛛网膜下腔出血、脑膜炎、颅内占位等严重疾病。",
                "source": "NICE Clinical Guidelines",
                "source_type": "guideline",
                "url": "https://www.nice.org.uk/guidance/cg150",
                "year": "2023",
                "keywords": ["头痛", "危险信号", "急症", "就医"],
                "confidence": 0.98
            },
            {
                "id": "doc_004",
                "title": "非甾体抗炎药治疗头痛的循证评价",
                "content": "布洛芬(400-600mg)和萘普生(500-550mg)对偏头痛急性发作有效。对乙酰氨基酚(1000mg)对轻至中度头痛有效。曲普坦类药物是中重度偏头痛的一线治疗。应注意药物过度使用性头痛的风险，每月使用止痛药不宜超过10天。",
                "source": "Cochrane Database of Systematic Reviews",
                "source_type": "pubmed",
                "pmid": "34567892",
                "doi": "10.1002/14651858.CD009108",
                "year": "2022",
                "keywords": ["头痛", "治疗", "NSAIDs", "布洛芬"],
                "confidence": 0.94
            },
            # Fever and infection
            {
                "id": "doc_005",
                "title": "成人发热的评估与处理",
                "content": "发热定义为核心体温≥38°C。常见病因包括感染(最常见)、自身免疫疾病、恶性肿瘤等。评估应包括详细病史、体格检查和必要的实验室检查。对症治疗包括物理降温和退热药物。",
                "source": "中华内科杂志",
                "source_type": "pubmed",
                "pmid": "34567893",
                "year": "2023",
                "keywords": ["发热", "感染", "评估"],
                "confidence": 0.91
            },
            {
                "id": "doc_006",
                "title": "流感诊疗方案",
                "content": "流感是由流感病毒引起的急性呼吸道传染病。主要症状包括发热(常高热)、头痛、肌肉酸痛、乏力、咳嗽等。抗病毒治疗（奥司他韦、扎那米韦）应在发病48小时内开始，以获得最佳疗效。高危人群应优先接种流感疫苗。",
                "source": "国家卫生健康委员会",
                "source_type": "guideline",
                "url": "http://www.nhc.gov.cn/",
                "year": "2023",
                "keywords": ["流感", "抗病毒", "疫苗"],
                "confidence": 0.97
            },
            # Diabetes
            {
                "id": "doc_007",
                "title": "2型糖尿病综合管理指南",
                "content": "2型糖尿病管理目标：HbA1c<7%（个体化调整）。一线用药为二甲双胍。生活方式干预是基础，包括饮食控制、规律运动、戒烟限酒。定期监测并发症：眼底、肾功能、足部检查。",
                "source": "中华糖尿病杂志",
                "source_type": "guideline",
                "year": "2024",
                "keywords": ["糖尿病", "二甲双胍", "管理"],
                "confidence": 0.96
            },
            # Hypertension
            {
                "id": "doc_008",
                "title": "高血压诊断与治疗指南要点",
                "content": "高血压诊断标准：非同日3次血压≥140/90mmHg。治疗目标：<140/90mmHg，高危患者<130/80mmHg。一线药物包括ACEI/ARB、CCB、利尿剂、β受体阻滞剂。生活方式改变：限盐(<6g/d)、减重、戒烟、限酒、运动。",
                "source": "中国高血压防治指南",
                "source_type": "guideline",
                "year": "2023",
                "keywords": ["高血压", "诊断", "治疗"],
                "confidence": 0.96
            },
            # Meningitis warning
            {
                "id": "doc_009",
                "title": "细菌性脑膜炎的早期识别",
                "content": "细菌性脑膜炎三联征：发热、头痛、颈强直。其他表现包括意识障碍、畏光、皮疹（脑膜炎球菌）。Kernig征和Brudzinski征阳性有诊断意义。这是医学急症，需立即就医进行腰穿和经验性抗生素治疗。",
                "source": "Lancet Neurology",
                "source_type": "pubmed",
                "pmid": "34567894",
                "year": "2023",
                "keywords": ["脑膜炎", "急症", "头痛", "发热"],
                "confidence": 0.97
            },
            # Drug information
            {
                "id": "doc_010",
                "title": "布洛芬药物信息",
                "content": "布洛芬（Ibuprofen）是非甾体抗炎药(NSAID)。适应症：解热镇痛、抗炎。用法：成人200-400mg/次，每4-6小时一次，每日最大1200mg。禁忌：活动性消化道溃疡、严重心衰、对NSAIDs过敏。注意：胃肠道不良反应、肾功能影响。",
                "source": "DrugBank",
                "source_type": "drugbank",
                "drugbank_id": "DB01050",
                "year": "2024",
                "keywords": ["布洛芬", "NSAIDs", "止痛"],
                "confidence": 0.99
            }
        ]
    
    @property
    def is_connected(self) -> bool:
        return self._is_connected or self._mock_mode
    
    async def initialize(self):
        """Initialize Qdrant connection or use mock mode"""
        if self._mock_mode:
            logger.info("Vector service running in mock mode with sample documents")
            self._is_connected = True
            return
        
        try:
            from qdrant_client import QdrantClient
            self.client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port
            )
            # Test connection
            self.client.get_collections()
            self._is_connected = True
            logger.info("Connected to Qdrant")
        except Exception as e:
            logger.warning(f"Failed to connect to Qdrant: {e}. Using mock mode.")
            self._mock_mode = True
            self._is_connected = True
    
    async def close(self):
        """Close Qdrant connection"""
        self._is_connected = False
    
    async def search_documents(
        self, 
        query: str, 
        keywords: Optional[List[str]] = None,
        limit: int = 5
    ) -> List[Evidence]:
        """Search for relevant documents/literature"""
        results = []
        
        if self._mock_mode:
            # Simple keyword matching for mock mode
            query_lower = query.lower()
            all_keywords = [query_lower]
            if keywords:
                all_keywords.extend([k.lower() for k in keywords])
            
            scored_docs = []
            for doc in self._mock_documents:
                score = 0
                doc_text = f"{doc['title']} {doc['content']}".lower()
                doc_keywords = [k.lower() for k in doc.get('keywords', [])]
                
                for kw in all_keywords:
                    if kw in doc_text:
                        score += 2
                    if kw in doc_keywords:
                        score += 3
                
                if score > 0:
                    scored_docs.append((doc, score))
            
            # Sort by score and return top results
            scored_docs.sort(key=lambda x: x[1], reverse=True)
            
            for doc, score in scored_docs[:limit]:
                source_type = SourceType.OTHER
                if doc.get("source_type") == "pubmed":
                    source_type = SourceType.PUBMED
                elif doc.get("source_type") == "guideline":
                    source_type = SourceType.GUIDELINE
                elif doc.get("source_type") == "drugbank":
                    source_type = SourceType.DRUGBANK
                
                evidence = Evidence(
                    source=doc["source"],
                    source_type=source_type,
                    snippet=doc["content"][:300] + "..." if len(doc["content"]) > 300 else doc["content"],
                    pmid=doc.get("pmid"),
                    doi=doc.get("doi"),
                    url=doc.get("url"),
                    confidence=doc.get("confidence", 0.8),
                    publication_date=doc.get("year"),
                    section=doc.get("title")
                )
                results.append(evidence)
        
        return results
    
    async def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID"""
        if self._mock_mode:
            for doc in self._mock_documents:
                if doc["id"] == doc_id:
                    return doc
        return None


# Singleton instance
vector_service = VectorService()

