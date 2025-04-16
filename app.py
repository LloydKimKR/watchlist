import requests
import json
import os
import datetime
import io # 파일 다운로드를 위해 io 모듈 임포트
from flask import Flask, send_file, make_response, render_template_string # Flask 및 관련 함수 임포트

# --- 기존 스크립트의 함수들 ---
# (fetch_binance_futures_symbols, filter_and_format_symbols 함수는 이전 코드와 동일)

# 바이낸스 선물 API 엔드포인트 (거래소 정보)
API_ENDPOINT = "https://fapi.binance.com/fapi/v1/exchangeInfo"

def fetch_binance_futures_symbols():
    """
    바이낸스 선물 API를 호출하여 USDT 무기한 계약 심볼 목록을 가져옵니다.
    (오류 발생 시 예외를 발생시켜 호출한 쪽에서 처리하도록 수정)
    """
    print("바이낸스 API에서 선물 거래소 정보를 가져오는 중...")
    response = requests.get(API_ENDPOINT, timeout=10)
    response.raise_for_status() # 요청 실패 시 예외 발생
    print("API 정보 수신 완료.")
    return response.json()

def filter_and_format_symbols(data):
    """
    API 응답 데이터에서 USDT 무기한 계약 심볼을 필터링하고
    'BINANCE:SYMBOLUSDT.P' 형식으로 포맷합니다.
    """
    if not data or 'symbols' not in data:
        print("유효한 심볼 데이터가 없습니다.")
        return []

    filtered_symbols = []
    print("USDT 무기한 계약 심볼 필터링 및 포맷 중...")
    for symbol_info in data['symbols']:
        if (symbol_info.get('contractType') == 'PERPETUAL' and
            symbol_info.get('quoteAsset') == 'USDT' and
            symbol_info.get('status') == 'TRADING'):
            symbol_name = symbol_info.get('symbol')
            if symbol_name:
                formatted_symbol = f"BINANCE:{symbol_name}.P"
                filtered_symbols.append(formatted_symbol)

    print(f"총 {len(filtered_symbols)}개의 심볼을 찾았습니다.")
    return filtered_symbols

# --- Flask 웹 애플리케이션 설정 ---

app = Flask(__name__) # Flask 앱 인스턴스 생성

# --- HTML 템플릿 ---
# 웹 페이지의 내용을 정의하는 HTML 코드 (Tailwind CSS 사용)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Binance 선물 심볼 다운로더</title>
    <script src="https://cdn.tailwindcss.com"></script> {# Tailwind CSS 로드 #}
    <style>
        body { font-family: 'Inter', sans-serif; } /* 기본 폰트 설정 */
    </style>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
</head>
<body class="bg-gray-100 flex items-center justify-center min-h-screen">
    <div class="bg-white p-8 rounded-lg shadow-md text-center">
        <h1 class="text-2xl font-bold mb-6 text-gray-800">Binance 선물 USDT 심볼 목록</h1>
        <p class="text-gray-600 mb-6">아래 버튼을 클릭하면 최신 심볼 목록을<br> <code class="bg-gray-200 px-1 rounded text-sm">BINANCE:SYMBOL.P</code> 형식의 .txt 파일로 다운로드합니다.</p>
        <button id="downloadBtn"
                onclick="startDownload()"
                class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-lg transition duration-300 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 inline-block mr-2" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
            심볼 목록 다운로드 (.txt)
        </button>
        <p id="status" class="text-sm text-gray-500 mt-4 h-5"></p> {# 상태 메시지 표시 영역 #}
    </div>

    <script>
        const downloadBtn = document.getElementById('downloadBtn');
        const statusP = document.getElementById('status');

        function startDownload() {
            statusP.textContent = '심볼 목록 생성 및 다운로드 준비 중...'; // 상태 업데이트
            downloadBtn.disabled = true; // 버튼 비활성화
            downloadBtn.classList.add('opacity-50', 'cursor-not-allowed');

            // '/download-symbols' 엔드포인트로 요청을 보내 다운로드를 트리거
            window.location.href = '/download-symbols';

            // 다운로드가 시작되면 (또는 약간의 지연 후) 버튼 상태를 되돌립니다.
            // 실제 다운로드 완료 시점을 정확히 알기는 어렵지만,
            // 사용자가 불편하지 않도록 적절한 시간 후에 버튼을 다시 활성화합니다.
            setTimeout(() => {
                statusP.textContent = '다운로드가 시작됩니다.';
                downloadBtn.disabled = false;
                downloadBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                // 잠시 후 상태 메시지 초기화
                setTimeout(() => { statusP.textContent = ''; }, 3000);
            }, 1500); // 1.5초 후 버튼 활성화 (네트워크 상태에 따라 조절 필요)
        }
    </script>
</body>
</html>
"""

# --- Flask 라우트 정의 ---

@app.route('/')
def index():
    """ 웹사이트의 메인 페이지를 보여줍니다. """
    # 위에서 정의한 HTML 문자열을 템플릿으로 렌더링하여 반환합니다.
    return render_template_string(HTML_TEMPLATE)

@app.route('/download-symbols')
def download_symbols():
    """ 심볼 목록을 생성하고 파일로 다운로드하는 엔드포인트입니다. """
    try:
        # 1. API에서 데이터 가져오기
        exchange_info = fetch_binance_futures_symbols()

        # 2. 심볼 필터링 및 포맷
        formatted_list = filter_and_format_symbols(exchange_info)

        if not formatted_list:
            # 처리할 심볼이 없을 경우 사용자에게 오류 메시지 반환 (간단한 텍스트로)
            return "처리할 USDT 무기한 계약 심볼을 찾지 못했습니다.", 404

        # 3. 파일 이름 생성 (날짜 포함)
        today_date = datetime.date.today()
        date_str = today_date.strftime("%y%m%d")
        # 'symbols'가 빠진 기본 파일 이름 사용
        base_name, extension = os.path.splitext("binance_futures_usdt.txt")
        final_filename = f"{base_name}_{date_str}{extension}"

        # 4. 파일 내용 생성 (쉼표로 구분된 문자열)
        output_string = ",".join(formatted_list)

        # 5. 메모리 내에서 파일 객체 생성
        # 문자열을 바이트로 인코딩하여 BytesIO 사용
        buffer = io.BytesIO()
        buffer.write(output_string.encode('utf-8'))
        buffer.seek(0) # 파일 포인터를 처음으로 이동

        # 6. Flask의 send_file을 사용하여 파일 다운로드 응답 생성
        return send_file(
            buffer, # 메모리 내 파일 객체
            mimetype='text/plain', # 파일 타입 지정
            as_attachment=True, # 첨부 파일로 다운로드하도록 설정
            download_name=final_filename # 다운로드될 파일 이름 지정
        )

    except requests.exceptions.RequestException as e:
        print(f"API 요청 오류: {e}")
        # 사용자에게 오류 메시지 반환
        return f"바이낸스 API 요청 중 오류가 발생했습니다: {e}", 500
    except Exception as e:
        print(f"서버 내부 오류: {e}")
        # 사용자에게 일반적인 오류 메시지 반환
        return f"심볼 목록 생성 중 서버 내부 오류가 발생했습니다: {e}", 500

# --- 서버 실행 ---
if __name__ == '__main__':
    # 개발 목적으로 debug=True 사용, 실제 배포 시에는 False로 변경하고
    # Waitress, Gunicorn 같은 WSGI 서버 사용 권장
    app.run(debug=True, host='0.0.0.0', port=5000)
    # host='0.0.0.0' 은 로컬 네트워크의 다른 기기에서도 접속 가능하게 함
    # port=5000 은 사용할 포트 번호 (다른 프로그램과 겹치지 않게 변경 가능)
