# coding: utf-8
"""
医疗知识图谱构建脚本
从 medical.json 导入数据到 Neo4j

使用方法:
    python build_kg.py

注意: 请确保 Neo4j 已启动，并修改下方的连接配置
"""

import os
import json
from py2neo import Graph, Node

# ========== Neo4j 连接配置 ==========
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "medical123"  # 请修改为你设置的密码
# ====================================


class MedicalGraph:
    def __init__(self):
        # 使用 os.path 处理路径，兼容 Windows 和 Linux
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_path = os.path.join(cur_dir, 'data', 'medical.json')
        
        print(f"正在连接 Neo4j: {NEO4J_URI}")
        try:
            # 指定默认数据库为 neo4j，并关闭路由以兼容单机 Desktop
            self.g = Graph(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD),
                name="neo4j",
                routing=False
            )
            print("✓ Neo4j 连接成功!")
        except Exception as e:
            print(f"✗ Neo4j 连接失败: {e}")
            raise

    def read_nodes(self):
        """读取医疗数据文件，解析节点和关系"""
        # 8类节点
        drugs = []  # 药品
        foods = []  # 食物
        checks = []  # 检查
        departments = []  # 科室
        producers = []  # 药品生产商
        diseases = []  # 疾病
        symptoms = []  # 症状
        cures = []  # 治疗方法

        disease_infos = []  # 疾病详细信息

        # 12种关系
        rels_department = []  # 科室-科室关系（小科室属于大科室）
        rels_noteat = []  # 疾病-忌吃食物
        rels_doeat = []  # 疾病-宜吃食物
        rels_recommandeat = []  # 疾病-推荐食物
        rels_commonddrug = []  # 疾病-常用药品
        rels_recommanddrug = []  # 疾病-推荐药品
        rels_check = []  # 疾病-检查项目
        rels_drug_producer = []  # 生产商-药物
        rels_cureway = []  # 疾病-治疗方式
        rels_symptom = []  # 疾病-症状
        rels_acompany = []  # 疾病-并发症
        rels_category = []  # 疾病-所属科室

        print(f"正在读取数据文件: {self.data_path}")
        count = 0
        
        for data in open(self.data_path, 'r', encoding='utf-8'):
            disease_dict = {}
            count += 1
            data_json = json.loads(data)
            disease = data_json['name']
            disease_dict['name'] = disease
            diseases.append(disease)
            
            # 初始化疾病属性
            disease_dict['desc'] = ''
            disease_dict['prevent'] = ''
            disease_dict['cause'] = ''
            disease_dict['easy_get'] = ''
            disease_dict['cure_lasttime'] = ''
            disease_dict['cured_prob'] = ''
            disease_dict['get_prob'] = ''

            # 解析症状
            if 'symptom' in data_json:
                symptoms += data_json['symptom']
                for symptom in data_json['symptom']:
                    rels_symptom.append([disease, symptom])

            # 解析并发症
            if 'acompany' in data_json:
                for acompany in data_json['acompany']:
                    rels_acompany.append([disease, acompany])

            # 解析疾病属性
            if 'desc' in data_json:
                disease_dict['desc'] = data_json['desc']
            if 'prevent' in data_json:
                disease_dict['prevent'] = data_json['prevent']
            if 'cause' in data_json:
                disease_dict['cause'] = data_json['cause']
            if 'get_prob' in data_json:
                disease_dict['get_prob'] = data_json['get_prob']
            if 'easy_get' in data_json:
                disease_dict['easy_get'] = data_json['easy_get']
            if 'cure_lasttime' in data_json:
                disease_dict['cure_lasttime'] = data_json['cure_lasttime']
            if 'cured_prob' in data_json:
                disease_dict['cured_prob'] = data_json['cured_prob']

            # 解析科室
            if 'cure_department' in data_json:
                cure_department = data_json['cure_department']
                if len(cure_department) == 1:
                    rels_category.append([disease, cure_department[0]])
                if len(cure_department) == 2:
                    big = cure_department[0]
                    small = cure_department[1]
                    rels_department.append([small, big])
                    rels_category.append([disease, small])
                departments += cure_department

            # 解析治疗方式
            if 'cure_way' in data_json:
                cure_way = data_json['cure_way']
                cures += cure_way
                for cure in cure_way:
                    rels_cureway.append([disease, cure])

            # 解析药品
            if 'common_drug' in data_json:
                common_drug = data_json['common_drug']
                for drug in common_drug:
                    rels_commonddrug.append([disease, drug])
                drugs += common_drug

            if 'recommand_drug' in data_json:
                recommand_drug = data_json['recommand_drug']
                drugs += recommand_drug
                for drug in recommand_drug:
                    rels_recommanddrug.append([disease, drug])

            # 解析食物
            if 'not_eat' in data_json:
                not_eat = data_json['not_eat']
                for _not in not_eat:
                    rels_noteat.append([disease, _not])
                foods += not_eat

            if 'do_eat' in data_json:
                do_eat = data_json['do_eat']
                for _do in do_eat:
                    rels_doeat.append([disease, _do])
                foods += do_eat

            if 'recommand_eat' in data_json:
                recommand_eat = data_json['recommand_eat']
                for _recommand in recommand_eat:
                    rels_recommandeat.append([disease, _recommand])
                foods += recommand_eat

            # 解析检查项目
            if 'check' in data_json:
                check = data_json['check']
                for _check in check:
                    rels_check.append([disease, _check])
                checks += check

            # 解析药品生产商
            if 'drug_detail' in data_json:
                drug_detail = data_json['drug_detail']
                producer = [i.split('(')[0] for i in drug_detail]
                rels_drug_producer += [[i.split('(')[0], i.split('(')[-1].replace(')', '')] for i in drug_detail]
                producers += producer

            disease_infos.append(disease_dict)

        print(f"✓ 读取完成，共 {count} 条疾病记录")
        
        return (set(drugs), set(foods), set(checks), set(departments), 
                set(producers), set(symptoms), set(diseases), set(cures), 
                disease_infos, rels_check, rels_recommandeat, rels_noteat, 
                rels_doeat, rels_department, rels_commonddrug, rels_drug_producer, 
                rels_recommanddrug, rels_symptom, rels_acompany, rels_category, rels_cureway)

    def create_node(self, label, nodes):
        """创建普通节点"""
        count = 0
        total = len(nodes)
        for node_name in nodes:
            node = Node(label, name=node_name)
            self.g.create(node)
            count += 1
            if count % 100 == 0:
                print(f"  {label}: {count}/{total}")
        print(f"  ✓ {label}: {count} 个节点创建完成")
        return

    def create_diseases_nodes(self, disease_infos):
        """创建疾病节点（包含详细属性）"""
        count = 0
        total = len(disease_infos)
        for disease_dict in disease_infos:
            node = Node("Disease", 
                        name=disease_dict['name'], 
                        desc=disease_dict['desc'],
                        prevent=disease_dict['prevent'], 
                        cause=disease_dict['cause'],
                        easy_get=disease_dict['easy_get'], 
                        cure_lasttime=disease_dict['cure_lasttime'],
                        cured_prob=disease_dict['cured_prob'],
                        get_prob=disease_dict.get('get_prob', ''))
            self.g.create(node)
            count += 1
            if count % 100 == 0:
                print(f"  Disease: {count}/{total}")
        print(f"  ✓ Disease: {count} 个节点创建完成")
        return

    def create_graphnodes(self):
        """创建所有节点"""
        print("\n========== 开始创建节点 ==========")
        
        (Drugs, Foods, Checks, Departments, Producers, Symptoms, Diseases, Cures,
         disease_infos, rels_check, rels_recommandeat, rels_noteat, rels_doeat, 
         rels_department, rels_commonddrug, rels_drug_producer, rels_recommanddrug,
         rels_symptom, rels_acompany, rels_category, rels_cureway) = self.read_nodes()
        
        print(f"\n节点统计:")
        print(f"  - 疾病 (Disease): {len(disease_infos)}")
        print(f"  - 药品 (Drug): {len(Drugs)}")
        print(f"  - 食物 (Food): {len(Foods)}")
        print(f"  - 检查 (Check): {len(Checks)}")
        print(f"  - 科室 (Department): {len(Departments)}")
        print(f"  - 生产商 (Producer): {len(Producers)}")
        print(f"  - 症状 (Symptom): {len(Symptoms)}")
        print(f"  - 治疗方式 (Cure): {len(Cures)}")
        
        print("\n创建节点中...")
        self.create_diseases_nodes(disease_infos)
        self.create_node('Drug', Drugs)
        self.create_node('Food', Foods)
        self.create_node('Check', Checks)
        self.create_node('Department', Departments)
        self.create_node('Producer', Producers)
        self.create_node('Symptom', Symptoms)
        self.create_node('Cure', Cures)
        
        print("\n✓ 所有节点创建完成!")
        return

    def create_relationship(self, start_node, end_node, edges, rel_type, rel_name):
        """创建关系"""
        # 去重
        set_edges = []
        for edge in edges:
            set_edges.append('###'.join(edge))
        
        count = 0
        total = len(set(set_edges))
        
        for edge in set(set_edges):
            edge = edge.split('###')
            p = edge[0]
            q = edge[1]
            # 转义单引号
            p = p.replace("'", "\\'")
            q = q.replace("'", "\\'")
            
            query = f"MATCH (p:{start_node}),(q:{end_node}) WHERE p.name='{p}' AND q.name='{q}' CREATE (p)-[rel:{rel_type}{{name:'{rel_name}'}}]->(q)"
            try:
                self.g.run(query)
                count += 1
                if count % 500 == 0:
                    print(f"  {rel_type}: {count}/{total}")
            except Exception as e:
                pass  # 忽略重复关系等错误
        
        print(f"  ✓ {rel_type} ({rel_name}): {count} 条关系创建完成")
        return

    def create_graphrels(self):
        """创建所有关系"""
        print("\n========== 开始创建关系 ==========")
        
        (Drugs, Foods, Checks, Departments, Producers, Symptoms, Diseases, Cures,
         disease_infos, rels_check, rels_recommandeat, rels_noteat, rels_doeat, 
         rels_department, rels_commonddrug, rels_drug_producer, rels_recommanddrug,
         rels_symptom, rels_acompany, rels_category, rels_cureway) = self.read_nodes()
        
        print("\n关系统计:")
        print(f"  - 疾病-症状: {len(rels_symptom)}")
        print(f"  - 疾病-并发症: {len(rels_acompany)}")
        print(f"  - 疾病-科室: {len(rels_category)}")
        print(f"  - 疾病-检查: {len(rels_check)}")
        print(f"  - 疾病-治疗方式: {len(rels_cureway)}")
        print(f"  - 疾病-常用药品: {len(rels_commonddrug)}")
        print(f"  - 疾病-推荐药品: {len(rels_recommanddrug)}")
        print(f"  - 疾病-宜吃食物: {len(rels_doeat)}")
        print(f"  - 疾病-忌吃食物: {len(rels_noteat)}")
        print(f"  - 疾病-推荐食物: {len(rels_recommandeat)}")
        print(f"  - 科室-科室: {len(rels_department)}")
        print(f"  - 生产商-药品: {len(rels_drug_producer)}")
        
        print("\n创建关系中...")
        self.create_relationship('Disease', 'Symptom', rels_symptom, 'has_symptom', '症状')
        self.create_relationship('Disease', 'Disease', rels_acompany, 'acompany_with', '并发症')
        self.create_relationship('Disease', 'Department', rels_category, 'belongs_to', '所属科室')
        self.create_relationship('Disease', 'Check', rels_check, 'need_check', '诊断检查')
        self.create_relationship('Disease', 'Cure', rels_cureway, 'cure_way', '治疗方法')
        self.create_relationship('Disease', 'Drug', rels_commonddrug, 'common_drug', '常用药品')
        self.create_relationship('Disease', 'Drug', rels_recommanddrug, 'recommand_drug', '好评药品')
        self.create_relationship('Disease', 'Food', rels_doeat, 'do_eat', '宜吃')
        self.create_relationship('Disease', 'Food', rels_noteat, 'no_eat', '忌吃')
        self.create_relationship('Disease', 'Food', rels_recommandeat, 'recommand_eat', '推荐食谱')
        self.create_relationship('Department', 'Department', rels_department, 'belongs_to', '属于')
        self.create_relationship('Producer', 'Drug', rels_drug_producer, 'drugs_of', '生产药品')
        
        print("\n✓ 所有关系创建完成!")
        return

    def clear_graph(self):
        """清空图数据库（谨慎使用）"""
        print("正在清空数据库...")
        self.g.run("MATCH (n) DETACH DELETE n")
        print("✓ 数据库已清空")


def main():
    print("=" * 50)
    print("    医疗知识图谱构建工具")
    print("=" * 50)
    
    handler = MedicalGraph()
    
    # 询问是否清空数据库
    print("\n是否清空现有数据库？(y/n，默认n): ", end="")
    try:
        choice = input().strip().lower()
    except:
        choice = 'n'
    
    if choice == 'y':
        handler.clear_graph()
    
    # 创建节点
    handler.create_graphnodes()
    
    # 创建关系
    handler.create_graphrels()
    
    print("\n" + "=" * 50)
    print("    知识图谱构建完成!")
    print("=" * 50)
    print("\n你可以打开 Neo4j Browser (http://localhost:7474) 查看结果")
    print("示例查询: MATCH (n:Disease) RETURN n LIMIT 10")


if __name__ == '__main__':
    main()

