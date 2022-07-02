# Gremlin Python SDK

[配置说明](./CONFIG.md)

## application graph

维护微服务信息（名字和故障注入代理地址）和依赖关系。

## failure generator

根据总体故障方案，生成对每个微服务注入的故障，通过代理注入

### 上层故障

中止请求、中止回复、延迟请求、延迟回复、
服务过载、服务分区、服务崩溃

### 选择器

起点、终点，消息类型（请求、回复、发布、订阅），
匹配规则（HTTP头X-Gremlin-ID、HTTP消息体）

### 底层故障

延迟、中止、篡改

## assertion checker

相当于进行HTTP请求，并验证返回的结果

### HTTP接口

http://{checklist.json log_server}/gremlin/_search

### 示例请求体

```json
{
  "size": 2000000000,
  "query": {
    "filtered": {
      "query": {
        "match_all": {}
      },
      "filter": {
        "bool": {
          "must": [
            {
              "term": {
                "msg": "Request"
              }
            },
            {
              "term": {
                "source": "productpage"
              }
            },
            {
              "term": {
                "dest": "reviews"
              }
            },
            {
              "term": {
                "testid": "d98541151c234211824da3ccbfd50349"
              }
            }
          ]
        }
      }
    }
  }
}
```

### 示例返回值

```json
{
  "took": 4,
  "timed_out": false,
  "_shards": {
    "total": 5,
    "successful": 5,
    "failed": 0
  },
  "hits": {
    "total": 1,
    "max_score": 1.0,
    "hits": [
      {
        "_index": "gremlin",
        "_type": "logs",
        "_id": "AYGn5V0vHOtM-wSapa9h",
        "_score": 1.0,
        "_source": {
          "actions": "[delay]",
          "delaytime": 8000,
          "dest": "reviews",
          "errorcode": -2,
          "level": "info",
          "msg": "Request",
          "protocol": "http",
          "reqID": "testUser-timeout-1651",
          "rule": {
            "source": "productpage",
            "dest": "reviews",
            "messagetype": "request",
            "bodypattern": "*",
            "headerpattern": "testUser-timeout-*",
            "delayprobability": 1,
            "delaydistribution": "uniform",
            "mangleprobability": 0,
            "mangledistribution": "uniform",
            "abortprobability": 0,
            "abortdistribution": "uniform",
            "delaytime": "8s",
            "errorcode": -1,
            "searchstring": "",
            "replacestring": ""
          },
          "source": "productpage",
          "testid": "d98541151c234211824da3ccbfd50349",
          "time": "2022-06-28T01:20:35Z",
          "trackingheader": "X-Gremlin-ID",
          "ts": "2022-06-28T01:20:27.616061",
          "uri": "/",
          "@version": "1",
          "@timestamp": "2022-06-28T01:20:35.629Z",
          "host": "192.168.128.6"
        }
      }
    ]
  }
}
```

---
生成包:

```commandline
python setup.py sdist
```
