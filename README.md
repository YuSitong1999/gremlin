# Gremlin
_**警告：引入的论文附带代码存在许多bug，尚未充分测试和修复！**_



## 简介
用于弹性测试（测试应用程序从云中常见的故障中恢复，从而保持服务可用的能力）的故障注入工具。

通过微服务间网络代理proxy支持注入基础故障，将故障注入结果经Logstash保存到ElasticSearch。

通过测试包sdk-python，支持将高层故障转化为基础故障，应用到网络代理proxy。支持通过在ElasticSearch搜索故障注入结果，检查是否符合预期。



## 组成
### proxy

使用Golang实现。

对容器外提供控制接口。支持对规则：新增、删除、显示、重置。对代理服务：获取、设置、移除。对测试ID：设置、移除。

在同一个容器范围内，对于每个依赖的外部微服务，相应启动一个代理服务，绑定本地端口，接收容器内应用的HTTP/TCP请求，请求外部微服务。

在请求前和回复前按设置的规则注入故障，当HTTP Header指定字段和Body匹配正则表达式时，注入基础故障：中止Abort、延迟Delay和篡改Modify。**论文提及的篡改Modify实际上暂未实现**。

故障注入的效果信息使用UDP发送到Logstash。

### sdk-python

使用Python3实现，论文附带的参考实现使用Python2实现。

#### application graph微服务依赖图
维护微服务信息（名字和故障注入代理地址）和依赖关系。

#### failure generator故障生成器
根据微服务依赖图和上层故障注入方案，生成对每个微服务注入的基础故障，通过网络代理proxy注入。

#### assertion checker断言检查器
请求ElasticSearch的故障注入结果信息，并验证返回的结果是否符合要求。

### Logstash和ElasticSearch
**使用论文附带的旧版本Logstash和ElasticSearch。**
Logstash接收故障注入结果信息，保存到ElasticSearch供搜索。


### demo
[demo README](./demo/README.md)




## 使用
### 环境
Golang 1.18

Python 3.9


### 准备
#### 构建proxy
在proxy目录执行以下命令，构建proxy
```bash
go mod download
go build -o gremlinproxy
```

#### 打包sdk-python成为gremlin
在sdk-python目录执行以下命令，打包gremlin到sdk-python/dist/gremlin-{version}.tar.gz
```bash
python setup.py sdist
```

### 运行proxy
参考[proxy README](./proxy/README.md)编写proxy配置文件，与之前构建的gremlinproxy一起，加入有发起请求的微服务所在的容器，并运行，比如：
```bash
/gremlinproxy -c proxyconfig.json
```

同时修改微服务的请求端口。

### 编写python程序执行故障注入




## 可能的TODO
### 已实现
* 添加规则:检查规则中正则表达式正确性
* 不同故障概率不应该互相独立，各种故障概率总和为1时应该必然有故障
### proxy
* 篡改:实现篡改Modify
* 延迟:实现模拟低带宽导致的延迟
* 延迟:实现代理收到回复，与回复调用者之间的延迟
* 中止:实现连接过程中中止
* 删除规则:并发写后写数据丢失bug
* 测试对TCP请求注入

### sdk-python
* 测试支持的上层故障

### Logstash和ElasticSearch
* 使用新版本


## 参考资料
论文：《Gremlin: Systematic Resilience Testing of Microservices》

论文代码： [ResilienceTesting](https://github.com/ResilienceTesting)

fork： [YuSitong1999/gremlinproxy](https://github.com/YuSitong1999/gremlinproxy) 
[YuSitong1999/gremlinsdk-python](https://github.com/YuSitong1999/gremlinsdk-python)