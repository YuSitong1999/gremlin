#!/usr/bin/python
# -*- coding: utf-8 -*-

import datetime
import pprint
import re
import time
from collections import defaultdict, namedtuple

import isodate
from elasticsearch import Elasticsearch

GremlinTestResult = namedtuple('GremlinTestResult', ['success', 'errormsg'])
AssertionResult = namedtuple('AssertionResult', ['name', 'info', 'success', 'errormsg'])

max_query_results = 2 ** 31 - 1


def _parse_duration(s: str) -> datetime.timedelta:
    """从字符串中提取时间信息

    Args:
        s: 时间字符串,时间单位h m s ms us µs

    Returns:
        时间段
    """
    r = re.compile(r"((\d*(\.\d*)?)(\D+))", re.UNICODE)
    start = 0
    m = r.search(s, start)
    vals = defaultdict(lambda: 0.0)
    while m is not None:
        unit = m.group(4)
        try:
            value = float(m.group(2))
        except ValueError:
            print(s, unit, m.group(2))
            return datetime.timedelta()
        if unit == "h":
            vals["hours"] = value
        elif unit == 'm':
            vals["minutes"] = value
        elif unit == 's':
            vals["seconds"] = value
        elif unit == "ms":
            vals["milliseconds"] = value
        elif unit == "us" or unit == "µs":
            vals["microseconds"] = value
        else:
            raise "Unknown time unit"
        start = m.end(1)
        m = r.search(s, start)
    return datetime.timedelta(**vals)


def _check_value_recursively(key, val, haystack) -> bool:
    """递归检查是否有指定k-v对
    Check if there is key _key_ with value _val_ in the given dictionary.
    ..warning:
        This is geared at JSON dictionaries, so some corner cases are ignored,
        we assume all iterables are either arrays or dicts
    """
    if isinstance(haystack, list):
        return any([_check_value_recursively(key, val, l) for l in haystack])
    elif isinstance(haystack, dict):
        if key not in haystack:
            return any([_check_value_recursively(key, val, d) for k, d in haystack.items()
                        if isinstance(d, list) or isinstance(d, dict)])
        else:
            return haystack[key] == val
    else:
        return False


def _get_by(key, val, l):
    """
    Out of list *l* return all elements that have *key=val*
    This comes in handy when you are working with aggregated/bucketed queries
    """
    return [x for x in l if _check_value_recursively(key, val, x)]


def _get_by_id(ID, l):
    """
    A convenience wrapper over _get_by
    that fetches things based on the "reqID" field
    """
    return _get_by("reqID", ID, l)


class AssertionChecker(object):
    """断言检查器 The assertion checker"""

    def __init__(self, host, test_id, debug=False):
        """
        Args:
            host: the elasticsearch host
            test_id: id of the test to which we are restricting the queries
        """
        self._es = Elasticsearch(host)
        self._id = test_id
        self.debug = debug
        self.functiondict = {
            'no_proxy_errors': self.check_no_proxy_errors,
            'bounded_response_time': self.check_bounded_response_time,
            'http_success_status': self.check_http_success_status,
            'http_status': self.check_http_status,
            'bounded_retries': self.check_bounded_retries,
            'circuit_breaker': self.check_circuit_breaker,
            'at_most_requests': self.check_at_most_requests
        }

    def _check_non_zero_results(self, data) -> bool:
        """确认elasticsearch返回值不为空"""
        return data["hits"]["total"] != 0 and len(data["hits"]["hits"]) != 0

    # was ProxyErrorsBad
    def check_no_proxy_errors(self, **kwargs) -> GremlinTestResult:
        """代理本身相关的主要错误
        Helper method to determine if the proxies logged any major errors related to the functioning of the proxy itself
        """
        data = self._es.search(body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "term": {
                            "level": "error"
                        }
                    }
                }
            }
        })
        #        if self.debug:
        #            print(data)
        return GremlinTestResult(data["hits"]["total"] == 0, data)

    # was ProxyErrors
    def get_requests_with_errors(self) -> GremlinTestResult:
        """ 代理传递的请求的错误
        Helper method to determine if proxies logged any error related to the requests passing through"""
        data = self._es.search(body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "exists": {
                            "field": "errmsg"
                        }
                    }
                }
            }
        })
        return GremlinTestResult(False, data)

    def check_bounded_response_time(self, **kwargs) -> GremlinTestResult:
        """检查返回时间
        对于当前测试，对指定起点、终点和时间限制，返回未超时 或 超时回复的相关信息，多个超时返回最后一个
        """
        assert 'source' in kwargs and 'dest' in kwargs and 'max_latency' in kwargs
        dest = kwargs['dest']
        source = kwargs['source']
        max_latency = _parse_duration(kwargs['max_latency'])
        data = self._es.search(body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "bool": {
                            "must": [
                                {"term": {"msg": "Response"}},
                                {"term": {"source": source}},
                                {"term": {"dest": dest}},
                                {"term": {"testid": self._id}}
                            ]
                        }
                    }
                }
            }
        })
        if self.debug:
            pprint.pprint(data)

        result = True
        errormsg = ""
        if not self._check_non_zero_results(data):
            result = False
            errormsg = "No log entries found"
            return GremlinTestResult(result, errormsg)

        for message in data["hits"]["hits"]:
            if _parse_duration(message['_source']["duration"]) > max_latency:
                result = False
                # Request ID from service did not
                errormsg = "{} did not reply in time for request {}, {}".format(
                    dest, message['_source']["reqID"], message['_source']["duration"])
                if self.debug:
                    print(errormsg)
        return GremlinTestResult(result, errormsg)

    def check_http_success_status(self, **kwargs) -> GremlinTestResult:
        """检查HTTP请求均成功返回200"""  # FIXME 成功且返回其他值?
        data = self._es.search(body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "exists": {
                            "field": "status"
                        }
                    }
                }
            }})
        result = True
        errormsg = ""
        if not self._check_non_zero_results(data):
            result = False
            errormsg = "No log entries found"
            return GremlinTestResult(result, errormsg)

        for message in data["hits"]["hits"]:
            if message['_source']["status"] != 200:
                if self.debug:
                    print(message['_source'])
                result = False
        return GremlinTestResult(result, errormsg)

    # check if the interaction between a given pair of services resulted in the required response status
    def check_http_status(self, **kwargs) -> GremlinTestResult:
        """检查指定起点、终点和请求ID，是否均返回指定 HTTP 状态"""
        assert 'source' in kwargs and 'dest' in kwargs and 'status' in kwargs and 'req_id' in kwargs
        source = kwargs['source']
        dest = kwargs['dest']
        status = kwargs['status']
        req_id = kwargs['req_id']
        data = self._es.search(body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "bool": {
                            "must": [
                                {"term": {"msg": "Response"}},
                                {"term": {"source": source}},
                                {"term": {"dest": dest}},
                                {"term": {"req_id": req_id}},
                                {"term": {"protocol": "http"}},
                                {"term": {"testid": self._id}}
                            ]
                        }
                    }
                }
            }})

        result = True
        errormsg = ""
        if not self._check_non_zero_results(data):
            result = False
            errormsg = "No log entries found"
            return GremlinTestResult(result, errormsg)

        for message in data["hits"]["hits"]:
            if message['_source']["status"] != status:
                if self.debug:
                    print(message['_source'])
                result = False
        return GremlinTestResult(result, errormsg)

    def check_at_most_requests(self, source, dest, num_requests, **kwargs) -> GremlinTestResult:
        """起点到终点，不同请求ID的HTTP请求数，均不超过指定值
        Check that source service sent at most num_request to the dest service
        Args:
            source: the source service name
            dest: the destination service name
            num_requests: the maximum number of requests that we expect
        """
        # TODO: Does the proxy support logging of instances so that grouping by instance is possible?

        if self.debug:
            print('in check_at_most_requests (%s, %s, %s, %s)' % (source, dest, num_requests, self._id))

        # Fetch requests for src->dst
        data = self._es.search(body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "bool": {
                            "must": [
                                {"term": {"msg": "Request"}},
                                {"term": {"source": source}},
                                {"term": {"dest": dest}},
                                {"term": {"protocol": "http"}},
                                {"term": {"testid": self._id}}
                            ]
                        }
                    }
                }
            },
            "aggs": {
                # Need size, otherwise only top buckets are returned
                # "size": max_query_results,
                # FIXME:所以现在只返回一个reqID?
                "byid": {
                    "terms": {
                        "field": "reqID",
                    }
                }
            }
        })
        # 返回值格式参考: https://www.elastic.co/guide/cn/elasticsearch/guide/current/_aggregation_test_drive.html

        if self.debug:
            pprint.pprint(data)

        result = True
        errormsg = ""
        if not self._check_non_zero_results(data):
            result = False
            errormsg = "No log entries found"
            return GremlinTestResult(result, errormsg)

        # Check number of requests in each bucket
        for bucket in data["aggregations"]["byid"]["buckets"]:
            if bucket["doc_count"] > (num_requests + 1):
                errormsg = "{} -> {} - expected {} requests, but found {} " \
                           "requests for id {}".format(source, dest, num_requests,
                                                       bucket['doc_count'] - 1, bucket['key'])
                result = False
                if self.debug:
                    print(errormsg)
                return GremlinTestResult(result, errormsg)
        return GremlinTestResult(result, errormsg)

    def check_bounded_retries(self, **kwargs):
        """有界重试"""
        assert 'source' in kwargs and 'dest' in kwargs and 'retries' in kwargs
        source = kwargs['source']
        dest = kwargs['dest']
        retries = kwargs['retries']  # 重试次数
        wait_time = kwargs.pop('wait_time', None)  # 重试间隔时间
        errdelta = kwargs.pop('errdelta', datetime.timedelta(milliseconds=10))  # 重试间隔时间允许的+-误差
        by_uri = kwargs.pop('by_uri', False)

        if self.debug:
            print('in bounded retries (%s, %s, %s)' % (source, dest, retries))

        data = self._es.search(body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "bool": {
                            "must": [
                                {"term": {"msg": "Request"}},
                                {"term": {"source": source}},
                                {"term": {"dest": dest}},
                                {"term": {"testid": self._id}}
                            ]
                        }
                    }
                }
            },
            "aggs": {
                "byid": {
                    "terms": {
                        "field": "reqID" if not by_uri else "uri",
                    }
                }
            }
        })

        if self.debug:
            pprint.pprint(data)

        result = True
        errormsg = ""
        if not self._check_non_zero_results(data):
            result = False
            errormsg = "No log entries found"
            return GremlinTestResult(result, errormsg)

        # Check number of req first
        for bucket in data["aggregations"]["byid"]["buckets"]:
            if bucket["doc_count"] > (retries + 1):
                errormsg = "{} -> {} - expected {} retries, but found {} retries for request {}".format(
                    source, dest, retries, bucket['doc_count'] - 1, bucket['key'])
                result = False
                if self.debug:
                    print(errormsg)
                return GremlinTestResult(result, errormsg)
        if wait_time is None:
            return GremlinTestResult(result, errormsg)

        wait_time = _parse_duration(wait_time)
        # Now we have to check the timestamps
        for bucket in data["aggregations"]["byid"]["buckets"]:
            req_id = bucket["key"]
            req_seq = _get_by_id(req_id, data["hits"]["hits"])
            # 按时间升序排序
            req_seq.sort(key=lambda x: isodate.parse_datetime(x['_source']["ts"]))
            for i in range(len(req_seq) - 1):
                # 检查重试间隔
                observed = isodate.parse_datetime(req_seq[i + 1]['_source']["ts"]) - \
                           isodate.parse_datetime(req_seq[i]['_source']["ts"])
                if not (((wait_time - errdelta) <= observed) or (observed <= (wait_time + errdelta))):
                    errormsg = "{} -> {} - expected {}+/-{}ms spacing for retry attempt {}, " \
                               "but request {} had a spacing of {}ms".format(
                        source, dest, wait_time, errdelta.microseconds / 1000, i + 1, req_id,
                                                 observed.microseconds / 1000)
                    result = False
                    if self.debug:
                        print(errormsg)
                    break
        return GremlinTestResult(result, errormsg)

    # remove_retries is a boolean argument.
    # Set to true if reties are attempted inside circuit breaker logic, else set to false
    def check_circuit_breaker(self, **kwargs):  # dest, closed_attempts, reset_time, halfopen_attempts):
        """断路器"""
        assert 'dest' in kwargs and 'source' in kwargs and 'closed_attempts' in kwargs and 'reset_time' in kwargs and 'headerprefix' in kwargs

        dest = kwargs['dest']
        source = kwargs['source']
        closed_attempts = kwargs['closed_attempts']
        reset_time = kwargs['reset_time']
        headerprefix = kwargs['headerprefix']
        if 'halfopen_attempts' not in kwargs:
            halfopen_attempts = 1
        else:
            halfopen_attempts = kwargs['halfopen_attempts']
        if 'remove_retries' not in kwargs:
            remove_retries = False
        else:
            remove_retries = kwargs['remove_retries']

        # TODO: 已针对阈值进行了测试，但未针对恢复进行测试
        #  this has been tested for thresholds but not for recovery
        # timeouts
        data = self._es.search(body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "bool": {
                            # FIXME 并列的must和should是逻辑与的关系，should必须匹配minimum_should_match个，
                            #  但只有HTTP请求有reqID,且HTTP msg必为Request/Response，不影响正确性
                            #  可能不同版本ES不同
                            "must": [
                                {"term": {"source": source}},
                                {"term": {"dest": dest}},
                                {"prefix": {"reqID": headerprefix}},
                                {"term": {"testid": self._id}}
                            ],
                            "should": [
                                {"term": {"msg": "Request"}},
                                {"term": {"msg": "Response"}},
                            ]
                        }
                    }
                }
            },
            "aggs": {
                "bysource": {
                    "terms": {
                        "field": "source",
                    }
                }
            }
        })

        if self.debug:
            # pprint.pprint(data)
            pprint.pprint(data["aggregations"]["bysource"]["buckets"])

        result = True
        errormsg = ""
        if not self._check_non_zero_results(data):
            result = False
            errormsg = "No log entries found"
            return GremlinTestResult(result, errormsg)

        reset_time = _parse_duration(reset_time)
        circuit_mode = "closed"  # 断路器状态

        # TODO - remove aggregations
        for bucket in data["aggregations"]["bysource"]["buckets"]:
            req_seq = _get_by("source", source, data["hits"]["hits"])
            req_seq.sort(key=lambda x: isodate.parse_datetime(x['_source']["ts"]))

            # 移除reqID重复的请求 Remove duplicate retries
            if remove_retries:
                req_seq_dup = []
                for i in range(len(req_seq)):
                    if i == len(req_seq) - 1:
                        req_seq_dup.append(req_seq[i])
                    elif req_seq[i]['_source']['reqID'] != req_seq[i + 1]['_source']['reqID']:
                        req_seq_dup.append(req_seq[i])

                req_seq = req_seq_dup

            failures = 0  # 闭合时失败次数
            circuit_open_ts = None  # 当前断开状态的开始时间
            successes = 0  # 半断开时成功次数
            print("starting " + circuit_mode)
            for req in req_seq:
                if circuit_mode == "open":  # circuit_open_ts is not None:
                    req_spacing = isodate.parse_datetime(req['_source']["ts"]) - circuit_open_ts
                    # 重置时间后，进入半断开模式 Restore to half-open
                    if req_spacing >= reset_time:
                        circuit_open_ts = None
                        circuit_mode = "half-open"
                        if self.debug:
                            print("%d: open -> half-open" % (failures + 1))
                        failures = 0  # -1
                    else:  # We are in open state
                        # 出错：断开时不应该进行请求 this is an assertion fail, no requests in open state
                        if req['_source']["msg"] == "Request":
                            if self.debug:
                                print("%d: open -> failure" % (failures + 1))
                            if self.debug:
                                print("Service %s failed to trip circuit breaker" % source)
                            errormsg = "{} -> {} - new request was issued at ({}s) before reset_timer ({}s)expired".format(
                                source, dest, req_spacing, reset_time)  # req['_source'])
                            result = False
                            break

                elif circuit_mode == "half-open":
                    if ((req['_source']["msg"] == "Response" and req['_source']["status"] != 200)
                            or (req['_source']["msg"] == "Request" and ("abort" in req['_source']["actions"]))):
                        # 半断开时请求中止 或 回复错误，断开
                        if self.debug:
                            print("half-open -> open")
                        circuit_mode = "open"
                        circuit_open_ts = isodate.parse_datetime(req['_source']["ts"])
                        successes = 0
                    elif req['_source']["msg"] == "Response" and req['_source']["status"] == 200:
                        # 半断开时回复成功，成功计数+1
                        successes += 1
                        if self.debug:
                            print("half-open -> half-open (%d)" % successes)
                        # 半断开成功一定次数，重新闭合 If over threshold, return to closed state
                        if successes > halfopen_attempts:
                            if self.debug:
                                print("half-open -> closed")
                            circuit_mode = "closed"
                            failures = 0
                            circuit_open_ts = None

                elif circuit_mode == "closed":
                    if ((req['_source']["msg"] == "Response" and req['_source']["status"] != 200)
                            or (req['_source']["msg"] == "Request" and len(req['_source']["actions"]) > 0)):
                        # 闭合时回复失败 或 请求中止，累计失败次数 Increment failures
                        failures += 1
                        if self.debug:
                            print("%d: closed->closed" % failures)
                        # print(failures)
                        # 失败超过门槛，断开 Trip CB, go to open state
                        if failures > closed_attempts:
                            if self.debug:
                                print("%d: closed->open" % failures)
                            circuit_open_ts = isodate.parse_datetime(req['_source']["ts"])
                            successes = 0
                            circuit_mode = "open"

        # pprint.pprint(data)
        return GremlinTestResult(result, errormsg)

    def check_num_requests(self, source: str, dest: str, num_requests: int, **kwargs) -> GremlinTestResult:
        """检查所有请求头，起点到终点的总请求数 TODO 未使用
        Check that source service sent at exactly num_request to the dest service, in total, for all request headers

        Args:
            source: the source service name
            dest: the destination service name
            num_requests: the maximum number of requests that we expect
        Returns:
            第一个请求数不一致的测试信息
        """

        if self.debug:
            print('in check_num_requests (%s, %s, %s, %s)' % (source, dest, num_requests, self._id))

        # Fetch requests for src->dst
        data = self._es.search(body={
            "size": max_query_results,
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "bool": {
                            "must": [
                                {"term": {"msg": "Request"}},
                                {"term": {"source": source}},
                                {"term": {"dest": dest}},
                                {"term": {"protocol": "http"}},
                                {"term": {"testid": self._id}}
                            ]
                        }
                    }
                }
            },
            "aggs": {
                "byid": {
                    "terms": {
                        "field": "testid",
                    }
                }
            }
        })

        if self.debug:
            pprint.pprint(data)
            pprint.pprint(data["aggregations"])

        result = True
        errormsg = ""
        if not self._check_non_zero_results(data):
            result = False
            errormsg = "No log entries found"
            return GremlinTestResult(result, errormsg)

        # Check number of requests in each bucket
        for bucket in data["aggregations"]["byid"]["buckets"]:
            if bucket["doc_count"] != num_requests:
                errormsg = "{} -> {} - expected {} requests, but found {} " \
                           "requests for id {}".format(source, dest, num_requests,
                                                       bucket['doc_count'], bucket['key'])
                result = False
                if self.debug:
                    print(errormsg)
                return GremlinTestResult(result, errormsg)
        return GremlinTestResult(result, errormsg)

    def check_bulkhead(self, source, dependencies, slow_dest, rate) -> GremlinTestResult:
        """检查隔板bulkhead,部分依赖变慢时，对其它依赖的请求速度不变 TODO 未使用
        Asserts bulkheads by ensuring that the rate of requests to other dests is kept when slow_dest is slow

        Args:
            source: the source service name
            dependencies: list of dependency names of source
            slow_dest: the name of the dependency that independence is being tested for
            rate: 每秒最少请求数 number of requests per second that should occur to each dependency

        Returns:
            检查结果
        """
        # Remove slow dest
        dependencies.remove(slow_dest)

        s = str(float(1) / float(rate))
        max_spacing = _parse_duration(s + 's')

        result: bool = True
        errormsg: str = ''

        for dest in dependencies:
            data = self._es.search(body={
                "size": max_query_results,
                "query": {
                    "filtered": {
                        "query": {
                            "match_all": {}
                        },
                        "filter": {
                            "bool": {
                                "must": [
                                    {"term": {"msg": "Request"}},
                                    {"term": {"source": source}},
                                    {"term": {"dest": dest}},
                                    {"term": {"testid": self._id}}
                                ]
                            }
                        }
                    }
                }
            })

            if self.debug:
                pprint.pprint(data)

            if not self._check_non_zero_results(data):
                result = False
                errormsg = "No log entries found"
                return GremlinTestResult(result, errormsg)

            req_seq = _get_by("source", source, data["hits"]["hits"])
            req_seq.sort(key=lambda x: isodate.parse_datetime(x['_source']["ts"]))

            last_request = isodate.parse_datetime(req_seq[0]['_source']["ts"])

            for req in req_seq:
                req_spacing = isodate.parse_datetime(req['_source']["ts"]) - last_request
                last_request = isodate.parse_datetime(req['_source']["ts"])
                if self.debug:
                    print("spacing", req_spacing, max_spacing)
                if req_spacing > max_spacing:
                    errormsg = "{} -> {} - new request was issued at ({}s) but max spacing should be ({}s)".format(
                        source,
                        dest,
                        req_spacing,
                        max_spacing)
                    result = False
                    return GremlinTestResult(result, errormsg)

        return GremlinTestResult(result, errormsg)

    def check_assertion(self, name=None, **kwargs) -> AssertionResult:
        """检查断言"""
        # assertion is something like {"name": "bounded_response_time",
        #                              "service": "productpage",
        #                              "max_latency": "100ms"}

        assert name is not None and name in self.functiondict
        gremlin_test_result = self.functiondict[name](**kwargs)

        if self.debug and not gremlin_test_result.success:
            print(gremlin_test_result.errormsg)

        return AssertionResult(name, str(kwargs), gremlin_test_result.success, gremlin_test_result.errormsg)

    def check_assertions(self, checklist: dict, all: bool = False) -> list[AssertionResult]:
        """检查断言集Check a set of assertions

        Args:
            checklist: ElasticSearch地址和断言信息
            all: False发现出错立即返回, True即使出错也全部检查完才返回
        """

        assert isinstance(checklist, dict) and 'checks' in checklist

        retlist: list[AssertionResult] = []

        for assertion in checklist['checks']:
            retval = self.check_assertion(**assertion)
            retlist.append(retval)
            if not retval.success and not all:
                print("Error message:", retval[3])
                return retlist

        return retlist
