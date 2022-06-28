package main

import (
	"flag"
	"fmt"
	"net"
	"os"
	"proxy/config"
	"proxy/router"

	"github.com/sirupsen/logrus"
)

func main() {
	// Read config
	// 读配置
	cpath := flag.String("c", "", "Path to the config file")
	flag.Parse()
	if *cpath == "" {
		fmt.Println("No config file specified.\nusage: gremlinproxy -c configfile")
		os.Exit(1)
	}
	conf := config.ReadConfig(*cpath)
	fmt.Println("Config read successful")

	var log = config.GlobalLogger
	// Log as JSON instead of the default ASCII formatter.
	if conf.LogJSON {
		log.Formatter = new(logrus.JSONFormatter)
	}

	if conf.LogstashHost != "" {
		// 尝试用UDP请求发送日志到log stash服务
		conn, err := net.Dial("udp", conf.LogstashHost)
		if err == nil {
			config.ProxyLogger.Out = conn
		} else {
			config.ProxyLogger.Out = os.Stderr
			config.ProxyLogger.Warn("Could not establish connection to logstash, logging to stderr")
		}
	} else { //else console
		config.ProxyLogger.Out = os.Stderr
	}
	// parse and set our log level
	if conf.LogLevel != "" {
		lvl, err := logrus.ParseLevel(conf.LogLevel)
		if err != nil {
			// default is info, if something went wrong
			log.Level = logrus.InfoLevel
			log.Error("Error parsing log level, defaulting to info")
		} else {
			log.Level = lvl
		}
	} else {
		log.Level = logrus.InfoLevel
	}

	// 必须设置要追踪的请求头
	config.TrackingHeader = conf.Router.TrackingHeader
	log.WithField("trackingHeader", config.TrackingHeader).Debug("Config value")
	if config.TrackingHeader == "" {
		panic("No trackingheader provided")
	}

	// Start the router
	r := router.NewRouter(conf)
	r.Run() //this blocks
}
