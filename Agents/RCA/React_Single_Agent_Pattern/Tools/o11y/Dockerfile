FROM golang:1.25.4 AS build

WORKDIR /app

# モジュールをコピーしてインストール
COPY go.mod go.sum ./
RUN go mod download

# ソースコードをコピー
COPY *.go ./

# バイナリをビルド（静的リンク）
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o main

# 最終的なランタイムイメージを作成
FROM alpine:latest

# バイナリをコピー
COPY --from=build /app/main /usr/bin/main

# 権限の設定
RUN chmod 755 /usr/bin/main
EXPOSE 8070

CMD [ "/usr/bin/main" ]