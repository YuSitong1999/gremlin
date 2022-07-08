# Demo

### timeout超时
请求依赖的微服务超时取消，返回缺省值。
### bounded_retry有界重试
请求依赖的微服务错误时，重试一定次数，重试有一定时间间隔。
### circuit_breaker断路器
生产环境中需要对所有请求，不只是HTTP Headers有指定字段的请求，注入故障，否则可能不会按预期断开。

有闭合、半断开和断开三种状态。闭合和半断开时正常请求依赖的微服务，断开时不发送请求，直接返回默认值（或缓存的旧值）。初始时为闭合状态。

闭合时，连续失败一定次数转为断开，记录断开开始时间。

断开时，经过一段时间，转为半断开。

半断开时，请求失败转为断开，记录断开时间；请求连续成功一定次数，转为闭合。


## 使用（以timeout为例）
### 环境
Golang 1.18

Python 3.9

Docker

### 准备
#### 构建proxy
在proxy目录执行以下命令，构建proxy
```bash
docker build -t gremlin-proxy .
```

#### 运行集群
在demo/timeout目录执行以下命令
```bash
docker-compose up -d
```

#### 打包sdk-python成为gremlin
在sdk-python目录执行以下命令，打包gremlin到sdk-python/dist/gremlin-{version}.tar.gz
```bash
python setup.py sdist
```

#### 安装gremlin包
pip install gremlin-{version}.tar.gz



### 运行
#### 运行故障注入
在demo\timeout\client运行
```bash
python .\main.py .\topology.json .\gremlins_{*}.json .\checklist.json
```
显示
```
test id: {testID}
Use `postman` to inject test requests,
	with HTTP header X-Gremlin-ID: <header-value>
	press Enter key to continue to validation phase
```

#### 发送请求
请求GET http://localhost:9080/

当设置HTTP Header中X-Gremlin-ID（完整或其中一部分）匹配正则表达式testUser-timeout-*，如果demo\timeout\cluster\main.go中设置的boundedTime足够小，请求将因注入延迟而超时取消，返回超时提示

当未设置X-Gremlin-ID或不匹配时，将正常返回

#### 检查故障注入结果

按Enter输出断言检查结果

