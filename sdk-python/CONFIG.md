# 配置说明

### 微服务依赖信息

services 微服务

* name 微服务名
* service_proxies 用于注入故障的代理地址

dependencies 依赖关系

* 依赖的微服务名
*
    * 被依赖的微服务名

例如：

```json
{
  "services": [
    {
      "name": "productpage",
      "service_proxies": [
        "127.0.0.1:9876"
      ]
    },
    {
      "name": "reviews"
    },
    {
      "name": "details"
    }
  ],
  "dependencies": {
    "productpage": [
      "reviews",
      "details"
    ]
  }
}
```

### 注入的故障信息

#### 故障类型

基础故障，源微服务与目的微服务至少有一个，概率分布缺省为uniform均匀分布，其它相关参数必须显式设置。

* abort_requests 中止请求
* abort_responses 中止回复
* delay_requests 延迟请求
* delay_responses 延迟回复


* overload_service 服务过载: 对目的微服务注入abort_requests和delay_requests，缺省概率各50%，延迟10s，中止返回503
* partition_services 服务网络分区：微服务互相之间请求中止abort_requests，缺省概率100%
* crash_service 服务崩溃: 对目的微服务注入abort_requests，缺省概率100%

#### 生成的故障信息

* source: 起点微服务名
* dest: 终点微服务名
* messagetype: 消息类型<request|response|publish|subscribe>
* headerpattern: 正则表达式匹配消息头中的proxy配置的键
* bodypattern: 正则表达式匹配消息体


* delayprobability: 延迟概率0.0 ~ 1.0
* delaydistribution: 延迟概率分布<uniform|exponential|normal> probability distribution function
* delaytime: 延迟时间<string> latency to inject into requests <string, e.g., "10ms", "1s", "5m", "3h", "1s500ms">


* mangleprobability: 修改概率0.0 ~ 1.0
* mangledistribution: 修改概率分布<uniform|exponential|normal> probability distribution function
* searchstring: 修改目标正则表达式<string> string to replace when Mangle is enabled
* replacestring: 修改后的字符串<string> string to replace with for Mangle fault


* abortprobability: 中止概率0.0 ~ 1.0
* abortdistribution: 中止概率分布<uniform|exponential|normal> probability distribution function
* errorcode: 中止返回值 HTTP error code or -1 to reset TCP connection

例子

```json
{
  "gremlins": [
    {
      "scenario": "abort_requests",
      "source": "productpage",
      "dest": "reviews",
      "headerpattern": "testUser-timeout-*",
      "bodypattern": "",
      "abortprobability": 1.0,
      "abortdistribution": "uniform",
      "errorcode": 404
    }
  ]
}
```

### 检查断言(待完善)
* bounded_response_time 超时: source dest max_latency
* bounded_retries 有界重试: source dest retries wait_time errdelta by_uri
* circuit_breaker 断路器: dest source closed_attempts reset_time headerprefix
* no_proxy_errors
* http_success_status
* http_status
* at_most_requests
