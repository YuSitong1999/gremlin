FROM alpine:3.15

WORKDIR /

COPY --from=gremlin-proxy /gremlinproxy /gremlinproxy
COPY gatewayconfig.json /gatewayconfig.json

EXPOSE 9080 9876

CMD [ "/gremlinproxy", "-c", "gatewayconfig.json" ]

