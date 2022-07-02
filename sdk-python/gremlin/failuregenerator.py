# coding=utf-8

import json
import logging
import uuid
import requests

# import httplib

from .applicationgraph import ApplicationGraph

logging.basicConfig()
requests_log = logging.getLogger("requests.packages.urllib3")


class Rule(object):

    def __init__(self, source: str, dest: str, messagetype: str,
                 headerpattern: str = "", bodypattern: str = "",
                 delayprobability: float = 0.0, delaydistribution: str = "uniform", delaytime: str = "0s",
                 mangleprobability: float = 0.0, mangledistribution: str = "uniform",
                 searchstring: str = "", replacestring: str = "",
                 abortprobability: float = 0.0, abortdistribution: str = "uniform", errorcode: int = -1):
        self.source = source
        self.dest = dest
        self.messagetype = messagetype
        self.headerpattern = headerpattern
        self.bodypattern = bodypattern

        self.delayprobability = delayprobability
        self.delaydistribution = delaydistribution
        self.delaytime = delaytime

        self.mangleprobability = mangleprobability
        self.mangledistribution = mangledistribution
        self.searchstring = searchstring
        self.replacestring = replacestring

        self.abortprobability = abortprobability
        self.abortdistribution = abortdistribution
        self.errorcode = errorcode

    def __str__(self) -> str:
        return str({"source": self.source,
                    "dest": self.dest,
                    "messagetype": self.messagetype,
                    "headerpattern": self.headerpattern,
                    "bodypattern": self.bodypattern,

                    "delayprobability": self.delayprobability,
                    "delaydistribution": self.delaydistribution,
                    "delaytime": self.delaytime,

                    "mangleprobability": self.mangleprobability,
                    "mangledistribution": self.mangledistribution,
                    "searchstring": self.searchstring,
                    "replacestring": self.replacestring,

                    "abortprobability": self.abortprobability,
                    "abortdistribution": self.abortdistribution,
                    "errorcode": self.errorcode
                    })


class FailureGenerator(object):

    def __init__(self, app: ApplicationGraph, debug=False):
        """创建一个新的失败生成器
        Create a new failure generator

        Args:
            app: ApplicationGraph instance of ApplicationGraph object
        """
        self.app: ApplicationGraph = app
        self.debug: bool = debug
        self._id: str or None = None
        self._queue: list[Rule] = list[Rule]()
        # some common scenarios
        self.functiondict = {
            'abort_requests': self.abort_requests,
            'abort_responses': self.abort_responses,
            'delay_requests': self.delay_requests,
            'delay_responses': self.delay_responses,
            'overload_service': self.overload_service,
            'partition_services': self.partition_services,
            'crash_service': self.crash_service
        }
        if debug:
            # httplib.HTTPConnection.debuglevel = 1
            logging.getLogger().setLevel(logging.DEBUG)
            requests_log.setLevel(logging.DEBUG)
            requests_log.propagate = True

    def start_new_test(self) -> str:
        """开始新测试，对所有已知代理设置新的随机测试ID"""
        self._id = uuid.uuid4().hex
        for service in self.app.get_services():
            if self.debug:
                print(service)
            for instance in self.app.get_service_instances(service):
                resp = requests.put("http://{}/gremlin/v1/test/{}".format(instance, self._id))
                resp.raise_for_status()
        return self._id

    def get_test_id(self):
        """当前测试ID"""
        return self._id

    def add_rule(self, rule: Rule):
        """增加规则"""
        self._queue.append(rule)

    def clear_rules_from_all_proxies(self):
        """清除已知代理之前注入的故障 Clear fault injection rules from all known service proxies."""
        self._queue = list[Rule]()
        if self.debug:
            print('Clearing rules')
        for service in self.app.get_services():
            for instance in self.app.get_service_instances(service):
                if self.debug:
                    print('Clearing rules for %s - instance %s' % (service, instance))
                resp = requests.delete("http://{}/gremlin/v1/rules".format(instance))
                if resp.status_code != 200:
                    print('Failed to clear rules for %s - instance %s' % (service, instance))

    def list_rules(self, service: str or None = None) -> dict[str: dict[str: any]]:
        """获取 所有微服务或指定微服务,所有代理当前注入的故障
            List fault fault injection rules installed on instances of a given service (or all services)
            returns a JSON dictionary
            Args:
                service: 可选 指定微服务
        """
        services: list[str] = list[str]()
        if service in self.app.get_services():
            services.append(service)

        rules: dict[str: dict[str: any]] = {}
        for service in services:
            rules[service] = {}
            for instance in self.app.get_service_instances(service):
                rules[service][instance] = {}
                resp = requests.get("http://{}/gremlin/v1/rules/list".format(instance))
                if resp.status_code != 200:
                    print('Failed to fetch rules from %s - instance %s' % (service, instance))
                    continue
                rules[service][instance] = resp.json()
        return rules

    def push_rules(self, continue_on_errors=False):
        """向代理添加故障规则
        Args:
            continue_on_errors: 请求失败时是否继续

        Raises:
            requests.exceptions.ConnectionError: 网络连接错误
        """
        for rule in self._queue:
            instances = self.app.get_service_instances(rule.source)
            for instance in instances:
                try:
                    resp = requests.post("http://{}/gremlin/v1/rules/add".format(instance),
                                         headers={"Content-Type": "application/json"},
                                         data=json.dumps(rule))
                    resp.raise_for_status()
                except requests.exceptions.ConnectionError as e:
                    print("FAILURE: Could not add rule to instance %s of service %s" % (instance, rule["source"]))
                    print(e)
                    if not continue_on_errors:
                        raise e

    def _generate_and_add_rules(self, rtypes: list[str], **args):
        """生成故障
        Args:
            rtypes: 涉及的基础故障类型

            args: 故障参数
            source: 起点微服务<source service name>
            dest: 终点微服务<destination service name>

            messagetype: 消息类型<request|response|publish|subscribe>

            headerpattern: 匹配消息头中的"X-Gremlin-ID" <regex to match against the value of the X-Gremlin-ID trackingheader present in HTTP headers>
            bodypattern: 匹配消息体 <regex to match against HTTP message body>

            delayprobability: <float, 0.0 to 1.0>
            delaydistribution: <uniform|exponential|normal> probability distribution function
            delaytime: <string> latency to inject into requests <string, e.g., "10ms", "1s", "5m", "3h", "1s500ms">

            mangleprobability: <float, 0.0 to 1.0>
            mangledistribution: <uniform|exponential|normal> probability distribution function
            searchstring: <string> string to replace when Mangle is enabled
            replacestring: <string> string to replace with for Mangle fault

            abortprobability: <float, 0.0 to 1.0>
            abortdistribution: <uniform|exponential|normal> probability distribution function
            errorcode: <Number> HTTP error code or -1 to reset TCP connection
        """

        source: str = args['source']
        dest: str = args['dest']
        source_correct: bool = source in self.app.get_services()
        dest_correct: bool = dest in self.app.get_services()
        assert source_correct or dest_correct

        sources: list[str] = []
        dests: list[str] = []
        if source_correct and dest_correct:
            sources.append(source)
            dests.append(dest)
        elif source_correct:
            sources.append(source)
            dests = self.app.get_dependencies(source)
        elif dest_correct:
            sources = self.app.get_dependents(dest)
            dests.append(dest)

        messagetype: str = args['messagetype']
        assert messagetype in ['request', 'response', 'publish', 'subscribe']

        headerpattern: str = args['headerpattern']
        bodypattern: str = args['bodypattern']
        assert isinstance(headerpattern, str)
        assert isinstance(bodypattern, str)

        assert len(rtypes) != 0
        for rtype in rtypes:
            assert rtype in ['delay', 'mangle', 'abort']

        delayprobability: float = 0.0
        delaydistribution: str = 'uniform'
        delaytime: str = "0s"
        mangleprobability: float = 0.0
        mangledistribution: str = 'uniform'
        searchstring: str = ''
        replacestring: str = ''
        abortprobability: float = 0.0
        abortdistribution: str = 'uniform'
        errorcode: int = -1

        if "delay" in rtypes:
            delayprobability = args['delayprobability']
            assert isinstance(delayprobability, float) and 0.0 < delayprobability <= 1.0
            delaydistribution: str = args.pop('delaydistribution', 'uniform')
            assert isinstance(delaydistribution, str) and delaydistribution in ['uniform', 'exponential', 'normal']
            delaytime: str = args['delaytime']
            assert isinstance(delaytime, str) and delaytime != ''

        if "mangle" in rtypes:
            mangleprobability: float = args['mangleprobability']
            assert isinstance(mangleprobability, float) and 0.0 < mangleprobability <= 1.0
            mangledistribution: str = args.pop('mangledistribution', 'uniform')
            assert isinstance(mangledistribution, str) and mangledistribution in ['uniform', 'exponential', 'normal']
            searchstring: str = args['searchstring']
            assert isinstance(searchstring, str) and searchstring != ''
            replacestring: str = args['replacestring']
            assert isinstance(replacestring, str)

        if "abort" in rtypes:
            abortprobability: float = args['abortprobability']
            assert isinstance(abortprobability, float) and 0.0 < abortprobability <= 1.0
            abortdistribution: str = args.pop('abortdistribution', 'uniform')
            assert isinstance(abortdistribution, str) and abortdistribution in ['uniform', 'exponential', 'normal']
            errorcode: int = args['errorcode']
            assert isinstance(errorcode, str) and errorcode != 0

        assert delayprobability + mangleprobability + abortprobability <= 1.0

        for s in sources:
            for d in dests:
                rule: Rule = Rule(s, d, messagetype, headerpattern, bodypattern,
                                  delayprobability, delaydistribution, delaytime,
                                  mangleprobability, mangledistribution, searchstring, replacestring,
                                  abortprobability, abortdistribution, errorcode)
                self.add_rule(rule)
                if self.debug:
                    print('%s - %s' % (rtypes, rule))

    def setup_failure(self, scenario: str, **args):
        """增加一个给定的故障方案 Add a given failure scenario
        Args:
            scenario: 添加故障的故障函数
        """
        assert scenario in self.functiondict
        self.functiondict[scenario](**args)

    def setup_failures(self, gremlins: dict[str, list[dict[str, any]]]):
        """Add gremlins to environment"""
        assert isinstance(gremlins, dict) and 'gremlins' in gremlins
        assert isinstance(gremlins['gremlins'], list)
        for gremlin in gremlins['gremlins']:
            self.setup_failure(**gremlin)
        self.push_rules()

    # 以下为各种类型故障

    def abort_requests(self, **args):
        args['messagetype'] = 'request'
        self._generate_and_add_rules(['abort'], **args)

    def abort_responses(self, **args):
        args['messagetype'] = 'response'
        self._generate_and_add_rules(['abort'], **args)

    def delay_requests(self, **args):
        args['messagetype'] = 'request'
        self._generate_and_add_rules(['delay'], **args)

    def delay_responses(self, **args):
        args['messagetype'] = 'response'
        self._generate_and_add_rules(['delay'], **args)

    def overload_service(self, **args):
        """实现服务过载，缺省50%延迟10s，另外50%返回HTTP 503
        Gives the impression of an overloaded service. If no probability is given
        50% of requests will be delayed by 10s (default) and rest 50% will get HTTP 503.
        """
        rule = args.copy()
        rule['source'] = ''
        assert isinstance(rule['dest'], str) and rule['dest'] != ''

        rule['messagetype'] = 'request'
        rule['headerpattern'] = rule.pop('headerpattern', '') or ''
        rule['bodypattern'] = rule.pop('bodypattern', '') or ''

        rule['delayprobability'] = rule.pop('delayprobability', 0.5) or 0.5
        rule['delaytime'] = rule.pop('delaytime', "10s") or "10s"
        rule['abortprobability'] = rule.pop('abortprobability', 0.5) or 0.5
        rule['errorcode'] = rule.pop("errorcode", 503) or 503

        self._generate_and_add_rules(['delay', 'abort'], **rule)

    def partition_services(self, **args):
        """两个服务之间网络分区，实现为互相之间一定概率请求中止
        Partitions two connected services. Not two sets of services (TODO)
        Expects usual arguments and srcprobability and dstprobability, that indicates probability of
        terminating connections from source to dest and vice versa
        """
        rule = args.copy()
        assert rule['dest'] in self.app.get_dependencies(rule['source'])

        rule['messagetype'] = 'request'

        rule['abortprobability'] = rule.pop('srcprobability', 1) or 1
        rule['errorcode'] = rule.pop('errorcode', -1) or -1
        self._generate_and_add_rules(['abort'], **rule)

        rule['abortprobability'] = rule.pop('dstprobability', 1) or 1
        rule['source'], rule['dest'] = rule['dest'], rule['source']
        self._generate_and_add_rules(['abort'], **rule)

    def crash_service(self, **args):
        """导致dest服务对所有调用者不可用,缺省100%概率  Causes the dest service to become unavailable to all callers"""
        rule = args.copy()
        assert 'source' not in rule
        rule['abortprobability'] = rule.pop('abortprobability', 1) or 1
        rule['errorcode'] = rule.pop('errorcode', -1) or -1
        self._generate_and_add_rules(['abort'], **rule)
