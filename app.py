import requests # ccxt 내부 또는 다른 용도로 필요할 수 있으므로 유지
import json
import os
import datetime
import io
import ccxt # ccxt 라이브러리 임포트
# request 객체를 사용하여 URL 파라미터를 읽어옵니다.
from flask import Flask, send_file, make_response, render_template_string, request

# --- API 엔드포인트 정의 (모두 제거 - ccxt 사용) ---

# --- Binance 데이터 처리 함수 (ccxt 사용) ---
def get_binance_symbols_ccxt():
    """ ccxt를 사용하여 Binance의 USDT 무기한 선물 심볼 목록을 가져오고 포맷합니다. """
    print("ccxt를 사용하여 Binance 마켓 정보 로드 중...")
    try:
        # ccxt.binance()는 현물, 선물 모두 포함하므로 그대로 사용
        exchange = ccxt.binance({
             'options': {
                 # 필요한 경우 기본 타입을 swap으로 지정 (선택 사항)
                 # 'defaultType': 'swap',
             }
        })
        # Binance의 모든 마켓 정보 로드
        markets = exchange.load_markets()
        print(f"Binance 마켓 정보 로드 완료. 총 {len(markets)}개 마켓.")

        filtered_symbols = []
        print("Binance USDT 무기한 선물(swap) 필터링 및 포맷 중...")

        # 로드된 마켓 정보를 순회하며 필터링
        for symbol, market in markets.items():
            # ccxt의 표준화된 속성을 사용하여 필터링:
            # 1. market['swap'] == True : 선물이면서 스왑(무기한) 계약인가?
            # 2. market['linear'] == True : USDT나 BUSD 등 스테이블 코인 기반 계약인가? (선형 계약)
            # 3. market['quote'] == 'USDT' : Quote 통화가 USDT인가?
            # 4. market['active'] == True : 현재 거래 가능한 마켓인가?
            if (market.get('swap', False) and
                market.get('linear', False) and
                market.get('quote') == 'USDT' and
                market.get('active', False)):

                # ccxt 심볼 형식 (예: 'BTC/USDT:USDT')을 원하는 형식으로 변환
                # ('BTC/USDT:USDT' -> 'BTCUSDT')
                ccxt_symbol = market['symbol']
                # ':USDT' 부분 제거 (선형 스왑 표시)
                base_quote = ccxt_symbol.split(':')[0]
                # '/' 제거
                formatted_name = base_quote.replace('/', '')

                # 최종 형식 생성 (예: 'BINANCE:BTCUSDT.P')
                formatted_symbol = f"BINANCE:{formatted_name}.P"
                filtered_symbols.append(formatted_symbol)

        print(f"총 {len(filtered_symbols)}개의 Binance USDT 무기한 선물 심볼을 찾았습니다.")
        return filtered_symbols

    except ccxt.NetworkError as e:
        print(f"Binance 네트워크 오류 (ccxt): {e}")
        raise requests.exceptions.RequestException(f"ccxt 네트워크 오류: {e}")
    except ccxt.ExchangeError as e:
        print(f"Binance 거래소 오류 (ccxt): {e}")
        raise requests.exceptions.RequestException(f"ccxt 거래소 오류: {e}")
    except Exception as e:
        print(f"Binance 심볼 처리 중 예상치 못한 오류 (ccxt): {e}")
        raise e

# --- BingX 데이터 처리 함수 (ccxt 사용 - 이전과 동일) ---
def get_bingx_symbols_ccxt():
    """ ccxt를 사용하여 BingX의 USDT 무기한 선물 심볼 목록을 가져오고 포맷합니다. """
    print("ccxt를 사용하여 BingX 마켓 정보 로드 중...")
    try:
        exchange = ccxt.bingx({
            'options': {}
        })
        markets = exchange.load_markets()
        print(f"BingX 마켓 정보 로드 완료. 총 {len(markets)}개 마켓.")

        filtered_symbols = []
        print("BingX USDT 무기한 선물(swap) 필터링 및 포맷 중...")

        for symbol, market in markets.items():
            if (market.get('swap', False) and
                market.get('linear', False) and
                market.get('quote') == 'USDT' and
                market.get('active', False)):
                ccxt_symbol = market['symbol']
                base_quote = ccxt_symbol.split(':')[0]
                formatted_name = base_quote.replace('/', '')
                formatted_symbol = f"BINGX:{formatted_name}.P"
                filtered_symbols.append(formatted_symbol)

        print(f"총 {len(filtered_symbols)}개의 BingX USDT 무기한 선물 심볼을 찾았습니다.")
        return filtered_symbols

    except ccxt.NetworkError as e:
        print(f"BingX 네트워크 오류 (ccxt): {e}")
        raise requests.exceptions.RequestException(f"ccxt 네트워크 오류: {e}")
    except ccxt.ExchangeError as e:
        print(f"BingX 거래소 오류 (ccxt): {e}")
        raise requests.exceptions.RequestException(f"ccxt 거래소 오류: {e}")
    except Exception as e:
        print(f"BingX 심볼 처리 중 예상치 못한 오류 (ccxt): {e}")
        raise e

# --- Flask 웹 애플리케이션 설정 ---
app = Flask(__name__)

# --- HTML 템플릿 (이전과 동일) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>거래소 심볼 다운로더</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style> body { font-family: 'Inter', sans-serif; } </style>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
</head>
<body class="bg-gray-100 flex items-center justify-center min-h-screen">
    <div class="bg-white p-8 rounded-lg shadow-md text-center">
        <h1 class="text-2xl font-bold mb-6 text-gray-800">거래소 선물 USDT 심볼 목록</h1>
        <p class="text-gray-600 mb-8">아래 버튼을 클릭하여 원하는 거래소의 최신 심볼 목록을<br> <code class="bg-gray-200 px-1 rounded text-sm">EXCHANGE:SYMBOL.P</code> 형식의 .txt 파일로 다운로드합니다.</p>

        <div class="space-y-4 md:space-y-0 md:space-x-4">
            {# Binance 다운로드 버튼 #}
            <button id="downloadBtnBinance"
                    onclick="startDownload('binance')"
                    class="w-full md:w-auto bg-yellow-500 hover:bg-yellow-600 text-white font-bold py-3 px-6 rounded-lg transition duration-300 ease-in-out focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:ring-opacity-50">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 inline-block mr-2" viewBox="0 0 20 20" fill="currentColor"><path d="M10.293 1.293a1 1 0 011.414 0l7 7a1 1 0 010 1.414l-7 7a1 1 0 01-1.414-1.414L15.586 11H3a1 1 0 110-2h12.586l-5.293-5.293a1 1 0 010-1.414z" clip-rule="evenodd"></path></svg> {# 아이콘 변경 가능 #}
                Binance 선물 목록 (.txt)
            </button>

            {# BingX 다운로드 버튼 #}
            <button id="downloadBtnBingx"
                    onclick="startDownload('bingx')"
                    class="w-full md:w-auto bg-blue-500 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-lg transition duration-300 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 inline-block mr-2" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
                BingX 선물 목록 (.txt)
            </button>
        </div>

        <p id="status" class="text-sm text-gray-500 mt-6 h-5"></p> {# 상태 메시지 표시 영역 #}
    </div>

    <script>
        const downloadBtnBinance = document.getElementById('downloadBtnBinance');
        const downloadBtnBingx = document.getElementById('downloadBtnBingx');
        const statusP = document.getElementById('status');

        // 다운로드 시작 함수 (거래소 이름 인자 추가)
        function startDownload(exchange) {
            let exchangeNameKr = exchange === 'binance' ? 'Binance' : 'BingX';
            statusP.textContent = `${exchangeNameKr} 심볼 목록 생성 및 다운로드 준비 중...`;

            // 모든 버튼 비활성화
            downloadBtnBinance.disabled = true;
            downloadBtnBingx.disabled = true;
            downloadBtnBinance.classList.add('opacity-50', 'cursor-not-allowed');
            downloadBtnBingx.classList.add('opacity-50', 'cursor-not-allowed');

            // '/download' 엔드포인트에 exchange 파라미터 추가하여 요청
            window.location.href = '/download?exchange=' + exchange;

            // 다운로드 시작 후 버튼 상태 복구 (시간 조절 필요)
            setTimeout(() => {
                statusP.textContent = `${exchangeNameKr} 다운로드가 시작됩니다.`;
                 // 모든 버튼 활성화
                downloadBtnBinance.disabled = false;
                downloadBtnBingx.disabled = false;
                downloadBtnBinance.classList.remove('opacity-50', 'cursor-not-allowed');
                downloadBtnBingx.classList.remove('opacity-50', 'cursor-not-allowed');
                setTimeout(() => { statusP.textContent = ''; }, 3000);
            }, 1500);
        }
    </script>
</body>
</html>
"""

# --- Flask 라우트 정의 (수정) ---

@app.route('/')
def index():
    """ 웹사이트의 메인 페이지를 보여줍니다. """
    return render_template_string(HTML_TEMPLATE)

# 다운로드 엔드포인트를 하나로 통합하고 exchange 파라미터로 구분
@app.route('/download')
def download_symbols():
    """ 요청된 거래소의 심볼 목록을 생성하고 파일로 다운로드합니다. """
    exchange = request.args.get('exchange', '').lower() # URL 파라미터에서 거래소 이름 가져오기

    process_func = None # 데이터 가져오기 + 필터링 + 포맷팅 함수
    exchange_prefix = ""
    base_filename_part = ""

    if exchange == 'binance':
        # Binance도 ccxt 사용 함수 호출
        process_func = get_binance_symbols_ccxt
        exchange_prefix = "BINANCE"
        base_filename_part = "binance_futures_usdt"
    elif exchange == 'bingx':
        # BingX는 ccxt 사용 함수 호출
        process_func = get_bingx_symbols_ccxt
        exchange_prefix = "BINGX"
        base_filename_part = "bingx_futures_usdt"
    else:
        return "잘못된 거래소입니다. 'binance' 또는 'bingx'를 지정해주세요.", 400

    try:
        # 1. 데이터 처리 함수 실행 (ccxt 호출, 필터링, 포맷팅 포함)
        formatted_list = process_func()

        if not formatted_list:
            return f"{exchange_prefix}에서 처리할 USDT 무기한 계약 심볼을 찾지 못했거나 처리 중 오류가 발생했습니다.", 404

        # 2. 파일 이름 생성
        today_date = datetime.date.today()
        date_str = today_date.strftime("%y%m%d")
        final_filename = f"{base_filename_part}_{date_str}.txt"

        # 3. 파일 내용 생성
        output_string = ",".join(formatted_list)

        # 4. 메모리 내 파일 객체 생성
        buffer = io.BytesIO()
        buffer.write(output_string.encode('utf-8'))
        buffer.seek(0)

        # 5. 파일 다운로드 응답 생성
        return send_file(
            buffer,
            mimetype='text/plain',
            as_attachment=True,
            download_name=final_filename
        )

    # ccxt 오류 및 requests 오류 모두 처리
    except requests.exceptions.RequestException as e:
        print(f"{exchange_prefix} API/네트워크 요청 오류: {e}")
        error_message = str(e)
        if "ccxt" in error_message.lower():
             user_message = f"{exchange_prefix} 거래소 정보 로드 중 오류 발생 (ccxt): {error_message}"
        else:
             # ccxt를 사용하므로 이 경우는 거의 발생하지 않음
             user_message = f"{exchange_prefix} 요청 중 오류 발생: {error_message}"
        return user_message, 500
    except Exception as e:
        print(f"{exchange_prefix} 서버 내부 오류: {e}")
        return f"{exchange_prefix} 심볼 목록 생성 중 서버 내부 오류가 발생했습니다: {e}", 500

# --- 서버 실행 ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

