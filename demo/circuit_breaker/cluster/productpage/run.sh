#!/bin/sh
echo "******Start Service******"
/productpage &
/gremlinproxy -c proxyconfig.json
