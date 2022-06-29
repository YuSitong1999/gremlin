# coding=utf-8
import networkx as nx


class ApplicationGraph(object):
    """代表Gremlin中测试的应用的拓朴关系
    Represent the topology of an application to be tested by Gremlin"""

    def __init__(self, model=None, debug=False):
        """初始化微服务应用依赖关系图

        Args:
            model: dependency graph of microservices with some details
                {
                    "services" : [
                        { "name": "gateway", "service_proxies": ["127.0.0.1:9877"] },
                        { "name": "productpage", "service_proxies": ["127.0.0.1:9876"] },
                        { "name": "reviews"},
                        { "name": "details"}
                    ],
                    "dependencies" : {
                        "gateway" : ["productpage"],
                        "productpage" : ["reviews", "details"]
                    }
                }
                services 微服务
                service_proxies 用于注入故障的代理地址
                dependencies 依赖关系
        """

        assert isinstance(debug, bool)
        assert model is None or isinstance(model, dict)

        self._graph = nx.DiGraph()
        self.debug = debug

        if model:
            assert 'services' in model and 'dependencies' in model
            for service in model['services']:
                self.add_service(**service)
            for source, destinations in model['dependencies'].items():
                assert isinstance(destinations, list)
                for destination in destinations:
                    self.add_dependency(source, destination)

    def add_service(self, name: str, service_proxies: list[str] = None):
        """向拓扑图中添加新的微服务

        Args:
            name: 微服务名字(无关主机名)
            service_proxies: 故障注入代理的地址
        """
        if service_proxies is None:
            service_proxies = []
        self._graph.add_node(name, instances=service_proxies)

    def add_dependency(self, from_server: str, to_server: str):
        """向拓扑图中添加新的微服务依赖关系

        Args:
            from_server: 依赖微服务的名字
            to_server: 被依赖微服务的名字
        """
        self._graph.add_edge(from_server, to_server)

    def get_dependents(self, service: str) -> list[str]:
        """获取依赖指定微服务的所有微服务

        Args:
            service: 被依赖微服务的名字
        """
        dservices = []
        for e in self._graph.in_edges(service):
            dservices.append(e[0])
        return dservices

    def get_dependencies(self, service) -> list[str]:
        """获取指定微服务依赖的所有微服务

        Args:
            service: 依赖微服务的名字
        """
        dservices = []
        for e in self._graph.out_edges(service):
            dservices.append(e[1])
        return dservices

    def get_services(self):
        """获取所有微服务
        """
        return self._graph.nodes()

    def get_service_instances(self, service) -> list[str]:
        """获取指定微服务所有故障注入代理地址

        Args:
            service: 微服务名字
        """
        instances: list[str] = list(dict(self._graph.nodes(data='instances'))[service])
        if instances is None:
            instances = list[str]()
        return instances

    def _get_networkx(self):
        """获取依赖图
        """
        return self._graph

    def __str__(self):
        retval = ""
        for node in self._graph.nodes():
            retval = retval + "Node: {}\n".format(node)
        for edge in self._graph.edges():
            retval = retval + "Edge: {}->{}\n".format(edge[0], edge[1])
        return retval
