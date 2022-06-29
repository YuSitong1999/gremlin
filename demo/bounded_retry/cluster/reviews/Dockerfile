FROM golang:1.16-alpine3.15 AS build

# Set destination for COPY
WORKDIR /

# Copy the source code. Note the slash at the end, as explained in
# https://docs.docker.com/engine/reference/builder/#copy
COPY go.mod .
COPY go.sum .
COPY *.go .

RUN go env -w GOPROXY=https://goproxy.cn
RUN go mod download
RUN go get github.com/gin-gonic/gin/binding@v1.8.1

# Build
RUN go build -o /reviews

FROM alpine:3.15

WORKDIR /
COPY --from=build /reviews /reviews

EXPOSE 9080

CMD [ "/reviews" ]
