package main

import (
	"context"
	"fmt"
	"github.com/gin-gonic/gin"
	"io/ioutil"
	"net/http"
	"strings"
	"time"
)

//var boundedTime = 5000 * time.Millisecond
var boundedTime = 30 * time.Millisecond

const detailsUrl = "http://localhost:9081/"
const reviewsUrl = "http://localhost:9082/"

func getData(url string, gremlinHeader string) (string, int) {
	request, _ := http.NewRequest("GET", url, nil)
	// 设置超时
	ctx, cancel := context.WithCancel(context.TODO())
	time.AfterFunc(boundedTime, func() { //
		cancel()
	})
	request = request.WithContext(ctx)

	// 设置请求头
	request.Header.Add("X-Gremlin-ID", gremlinHeader)

	// 获取服务器响应数据
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		fmt.Printf("getData http request error: %s", err.Error())
		return fmt.Sprintf("getData http request error: %s\n", err.Error()), http.StatusRequestTimeout
	}
	defer response.Body.Close()

	body, err := ioutil.ReadAll(response.Body)
	if err != nil {
		panic(err)
	}
	fmt.Printf(string(body))
	return string(body), response.StatusCode
}

func main() {
	r := gin.Default()
	r.GET("/", func(context *gin.Context) {
		gremlinHeader := context.Request.Header.Get("X-Gremlin-ID")
		if gremlinHeader == "" {
			userType := context.Params.ByName("u")
			if strings.HasPrefix(userType, "test") {
				gremlinHeader = userType
			}
		}

		// call detail http api
		detailCode, detailString := getData(detailsUrl, gremlinHeader)

		// call review http api
		reviewCode, reviewString := getData(reviewsUrl, gremlinHeader)

		context.JSON(http.StatusOK, gin.H{
			"message":       "ok",
			"detail_code":   detailCode,
			"detail_string": detailString,
			"review_code":   reviewCode,
			"review_string": reviewString,
		})
	})
	r.Run("0.0.0.0:9080")
}
