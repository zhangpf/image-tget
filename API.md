# Coordinator和Client的接口设计方案

## 简介
采用REST风格的API，并且参考了openstack中镜像服务glance API的设计。

### peer向coordinator注册自己
POST /peers/<IP_ADDRESS>  
成功：202(Accepted) 成功注册  
失败：400(Bad Request) 注册失败，通常因为peer重复注册自己

### peer向coordinator请求下载一个虚拟机镜像
GET /images/<IMAGE_ID>  
成功：200(OK) 并随后开始镜像的下载  
重定向：300(Multiple Choices) 返回peer的父亲节点  
失败：404(Not Found) 该镜像不存在

### peer向coordinator注销自己
DELETE /peers/<IP_ADDRESS>  
成功：202(Accepted) 成功注销  
失败：400(Bad Request) 注册失败，通常因为peer重复注销自己或自己本来就没有注册过

### peer向coordinator发心跳报告
PUT /peers/<IP_ADDRESS>  
成功：202(Accepted) 成功  
失败：400(Bad Request) 心跳失败
