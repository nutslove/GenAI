## GrafanaのWebhookアラートを受け取るサーバ
import http.server
import socketserver
import json
import urllib.parse
from datetime import datetime

class WebhookHandler(http.server.BaseHTTPRequestHandler):

    def do_POST(self):
        if self.path == '/webhook':
            self.handle_webhook()
        else:
            self.send_error(404, "Not Found")

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"message": "Webhook Server is running!"}
            self.wfile.write(json.dumps(response).encode())
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"status": "healthy"}
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_error(404, "Not Found")

    def handle_webhook(self):
        try:
            # ヘッダー情報を取得
            headers = dict(self.headers)
            content_length = int(self.headers.get('Content-Length', 0))

            print(f"\n=== Webhook受信 ({datetime.now()}) ===")
            print(f"Headers: {json.dumps(headers, indent=2, ensure_ascii=False)}")

            # POSTデータを読み取り
            if content_length > 0:
                post_data = self.rfile.read(content_length)

                # Content-Typeに基づいて処理
                content_type = self.headers.get('Content-Type', '')

                if 'application/json' in content_type:
                    # JSONデータ
                    try:
                        data = json.loads(post_data.decode('utf-8'))
                        print(f"JSON Data: {json.dumps(data, indent=2, ensure_ascii=False)}")
                        data_str = json.dumps(data, ensure_ascii=False)
                        for alert in data.get("alerts", []):
                            print(f"status: {alert.get('status')}, labels: {alert.get('labels')}, annotations: {alert.get('annotations')}")
                    except json.JSONDecodeError:
                        print(f"JSON解析エラー - Raw Data: {post_data.decode('utf-8')}")

                elif 'application/x-www-form-urlencoded' in content_type:
                    # フォームデータ
                    form_data = urllib.parse.parse_qs(post_data.decode('utf-8'))
                    # 値が配列になるので、単一値の場合は最初の要素を取得
                    simplified_data = {k: v[0] if len(v) == 1 else v for k, v in form_data.items()}
                    print(f"Form Data: {json.dumps(simplified_data, indent=2, ensure_ascii=False)}")

                else:
                    # その他のデータ
                    print(f"Raw Data: {post_data.decode('utf-8')}")
            else:
                print("No POST data received")

            # 成功レスポンスを返す
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"status": "received"}
            self.wfile.write(json.dumps(response).encode())

        except Exception as e:
            print(f"エラーが発生しました: {e}")
            self.send_error(500, f"Internal Server Error: {e}")

    def log_message(self, format, *args):
        """ログメッセージをカスタマイズ（不要なログを抑制）"""
        pass

def run_server(port=8088):
    """サーバを起動"""
    with socketserver.TCPServer(("", port), WebhookHandler) as httpd:
        print(f"Webhookサーバを起動中...")
        print(f"エンドポイント: http://localhost:{port}/webhook")
        print(f"ヘルスチェック: http://localhost:{port}/health")
        print(f"停止するには Ctrl+C を押してください")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nサーバを停止中...")
            httpd.shutdown()

if __name__ == "__main__":
    run_server(8089)