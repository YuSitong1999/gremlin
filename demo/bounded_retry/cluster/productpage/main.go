package main

import (
	"fmt"
	"github.com/gin-gonic/gin"
	"io/ioutil"
	"net/http"
	"strings"
	"time"
)

const retryTimes = 5

const detailsUrl = "http://localhost:9081/"
const reviewsUrl = "http://localhost:9082/"

func getData(url string, gremlinHeader string) (string, int) {
	request, _ := http.NewRequest("GET", url, nil)

	// 设置请求头
	request.Header.Add("X-Gremlin-ID", gremlinHeader)

	var response *http.Response
	var err error
	// 有界重试retryTimes
	for i := 0; i <= retryTimes; i++ {
		if i != 0 {
			fmt.Printf("retry %d\n", i)
		}
		// 获取服务器响应数据
		response, err = http.DefaultClient.Do(request)
		if err == nil && http.StatusOK <= response.StatusCode && response.StatusCode <= http.StatusIMUsed {
			break
		}
		time.Sleep(1 * time.Second)
	}
	if !(err == nil && http.StatusOK <= response.StatusCode && response.StatusCode <= http.StatusIMUsed) {
		fmt.Printf("getData http request error: %s", err.Error())
		return fmt.Sprintf("getData http request error: %s\n", err.Error()), http.StatusInternalServerError
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
