import requests
import json
import os
import datetime
import io
import ccxt # ccxt 라이브러리 임포트
from flask import Flask, send_file, make_response, render_template_string, request

# --- 통합 심볼 처리 함수 (ccxt 사용) ---
def get_symbols_ccxt(exchange_id, market_type):
    """
    ccxt를 사용하여 지정된 거래소와 마켓 타입의 심볼 목록을 가져오고 포맷합니다.

    Args:
        exchange_id (str): ccxt 거래소 ID (예: 'binance', 'gateio', 'upbit')
        market_type (str): 마켓 타입 ('futures', 'spot_usdt', 'spot_krw')

    Returns:
        list: 포맷팅된 심볼 문자열 리스트
    """
    print(f"ccxt: {exchange_id} ({market_type}) 마켓 정보 로드 시도...")
    try:
        # ccxt 거래소 객체 생성
        exchange_class = getattr(ccxt, exchange_id)
        # 일부 거래소는 특정 옵션이 필요할 수 있음 (예: Gate.io v4 API 명시)
        if exchange_id == 'gateio':
             exchange = exchange_class({'options': {'defaultType': 'swap'}}) # 선물/현물 모두 가져오도록 기본값 설정 시도
        else:
             exchange = exchange_class()


        # 마켓 정보 로드
        markets = exchange.load_markets()
        print(f"ccxt: {exchange_id} 마켓 정보 로드 완료. 총 {len(markets)}개 마켓.")

        filtered_symbols = []
        exchange_prefix = exchange_id.upper()
        print(f"ccxt: {exchange_prefix} ({market_type}) 필터링 및 포맷 중...")

        # 로드된 마켓 정보를 순회하며 필터링 및 포맷팅
        for symbol, market in markets.items():
            is_active = market.get('active', False)
            # Gate.io 같은 경우 active 필드가 null일 수 있음, None이 아니면 True로 간주
            if is_active is None and exchange_id == 'gateio':
                 is_active = True # Gate.io의 경우 None이 아닌 active 상태로 가정 (필요시 조정)

            formatted_symbol = None

            # 1. 선물 (USDT 무기한) 필터링 및 포맷
            if market_type == 'futures':
                is_swap = market.get('swap', False)
                is_linear = market.get('linear', False)
                quote = market.get('quote')
                # Gate.io는 'settle' 통화가 USDT인지 추가 확인 필요할 수 있음
                settle = market.get('settle')

                if is_swap and is_linear and quote == 'USDT' and is_active:
                     # Gate.io는 settle 통화도 USDT인지 확인 (더 정확한 필터링)
                     if exchange_id == 'gateio' and settle != 'USDT':
                          continue

                     ccxt_symbol = market['symbol']
                     # ':' 구분자가 없을 수도 있음 (예: Gate.io)
                     if ':' in ccxt_symbol:
                          base_quote = ccxt_symbol.split(':')[0]
                     else:
                          base_quote = ccxt_symbol # 예: BTC/USDT

                     formatted_name = base_quote.replace('/', '') # '/' 제거
                     formatted_symbol = f"{exchange_prefix}:{formatted_name}.P"

            # 2. 현물 (KRW) 필터링 및 포맷 (Upbit, Bithumb)
            elif market_type == 'spot_krw':
                is_spot = market.get('spot', False)
                quote = market.get('quote')
                if is_spot and quote == 'KRW' and is_active:
                    ccxt_symbol = market['symbol'] # 예: 'BTC/KRW'
                    formatted_name = ccxt_symbol.replace('/', '')
                    formatted_symbol = f"{exchange_prefix}:{formatted_name}"

            # 3. 현물 (USDT) 필터링 및 포맷 (그 외 거래소)
            elif market_type == 'spot_usdt':
                is_spot = market.get('spot', False)
                quote = market.get('quote')
                if is_spot and quote == 'USDT' and is_active:
                    ccxt_symbol = market['symbol'] # 예: 'BTC/USDT'
                    formatted_name = ccxt_symbol.replace('/', '')
                    formatted_symbol = f"{exchange_prefix}:{formatted_name}"

            # 포맷팅된 심볼이 있으면 리스트에 추가
            if formatted_symbol:
                filtered_symbols.append(formatted_symbol)

        print(f"ccxt: 총 {len(filtered_symbols)}개의 {exchange_prefix} ({market_type}) 심볼을 찾았습니다.")
        # 결과를 알파벳 순으로 정렬하여 반환
        return sorted(filtered_symbols)

    except AttributeError:
        print(f"오류: 지원하지 않는 거래소 ID '{exchange_id}' 또는 ccxt 모듈에 해당 클래스 없음.")
        raise ValueError(f"지원하지 않는 거래소 ID: {exchange_id}")
    except ccxt.NetworkError as e:
        print(f"{exchange_prefix} 네트워크 오류 (ccxt): {e}")
        raise requests.exceptions.RequestException(f"ccxt 네트워크 오류: {e}")
    except ccxt.ExchangeError as e:
        # Gate.io 등 일부 거래소는 load_markets 시 특정 오류를 반환할 수 있음
        print(f"{exchange_prefix} 거래소 오류 (ccxt): {e}")
        # 오류 메시지에 'fetchMarkets' 등이 포함되면 마켓 로딩 실패로 간주 가능
        if 'fetchMarkets' in str(e):
             print(f"경고: {exchange_prefix} 마켓 정보 로드 실패 가능성 있음.")
             return [] # 빈 리스트 반환하여 404 처리 유도
        raise requests.exceptions.RequestException(f"ccxt 거래소 오류: {e}")
    except Exception as e:
        print(f"{exchange_prefix} ({market_type}) 심볼 처리 중 예상치 못한 오류 (ccxt): {e}")
        raise e


# --- Flask 웹 애플리케이션 설정 ---
app = Flask(__name__)

# --- HTML 템플릿 (순서, 제목, 색상 등 수정) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>트레이딩뷰 최신 왓치리스트</title> {# 제목 변경 #}
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: 'Inter', sans-serif; }
        .exchange-group { margin-bottom: 1.5rem; padding-bottom: 1.5rem; border-bottom: 1px solid #e5e7eb; }
        .exchange-group:last-child { margin-bottom: 0; padding-bottom: 0; border-bottom: none; }
        .exchange-title { font-weight: 600; color: #374151; margin-bottom: 1rem; font-size: 1.1rem; }
        /* 버튼 기본 스타일 */
        .dl-button {
            width: 100%;
            font-weight: bold;
            padding-top: 0.5rem; padding-bottom: 0.5rem;
            padding-left: 1rem; padding-right: 1rem;
            border-radius: 0.375rem; /* rounded-md */
            transition: all 0.3s ease-in-out;
            border: 1px solid transparent; /* 테두리 공간 확보 */
        }
        /* 반응형 - 작은 화면 이상에서 너비 자동 */
        @media (min-width: 640px) {
            .dl-button { width: auto; }
        }
        /* 비활성화 스타일 */
        .dl-button:disabled { opacity: 0.5; cursor: not-allowed; }
        /* 호버 효과 공통 (밝기 조절) */
        .dl-button:not(:disabled):hover { filter: brightness(0.9); }

        /* 현물 버튼 스타일 (회색 배경) */
        .spot-button { background-color: #e5e7eb; color: #374151; /* bg-gray-200 text-gray-700 */ }
        .spot-button:hover:not(:disabled) { background-color: #d1d5db; /* hover:bg-gray-300 */ }

    </style>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
</head>
<body class="bg-gray-100 flex items-center justify-center min-h-screen py-12 px-4">
    <div class="bg-white p-6 md:p-8 rounded-lg shadow-lg text-center max-w-3xl w-full">
        <h1 class="text-2xl md:text-3xl font-bold mb-4 text-gray-800">트레이딩뷰 최신 왓치리스트</h1> {# 제목 변경 #}
        <p class="text-gray-600 mb-8">원하는 거래소와 마켓 타입의 버튼을 클릭하여<br>최신 심볼 목록(.txt)을 다운로드하세요.</p> {# 설명 변경 #}

        {# 순서 변경: Binance #}
        <div class="exchange-group">
            <h2 class="exchange-title">Binance</h2>
            <div class="space-y-3 sm:space-y-0 sm:space-x-3">
                <button onclick="startDownload('binance', 'futures')" class="dl-button text-black" style="background-color: #efb90b;">선물 (USDT)</button>
                <button onclick="startDownload('binance', 'spot_usdt')" class="dl-button spot-button">현물 (USDT)</button>
            </div>
        </div>

        {# 순서 변경: Bybit #}
        <div class="exchange-group">
            <h2 class="exchange-title">Bybit</h2>
             <div class="space-y-3 sm:space-y-0 sm:space-x-3">
                <button onclick="startDownload('bybit', 'futures')" class="dl-button text-white" style="background-color: #17181f;">선물 (USDT)</button>
                <button onclick="startDownload('bybit', 'spot_usdt')" class="dl-button spot-button">현물 (USDT)</button>
            </div>
        </div>

        {# 순서 변경: BingX #}
        <div class="exchange-group">
            <h2 class="exchange-title">BingX</h2>
             <div class="space-y-3 sm:space-y-0 sm:space-x-3">
                <button onclick="startDownload('bingx', 'futures')" class="dl-button text-white" style="background-color: #0f5fff;">선물 (USDT)</button>
                <button onclick="startDownload('bingx', 'spot_usdt')" class="dl-button spot-button">현물 (USDT)</button>
            </div>
        </div>

        {# 추가: Gate.io #}
        <div class="exchange-group">
            <h2 class="exchange-title">Gate.io</h2>
             <div class="space-y-3 sm:space-y-0 sm:space-x-3">
                <button onclick="startDownload('gateio', 'futures')" class="dl-button text-black" style="background-color: #31ffff;">선물 (USDT)</button>
                 <button onclick="startDownload('gateio', 'spot_usdt')" class="dl-button spot-button">현물 (USDT)</button>
           </div>
        </div>

        {# 순서 변경: Bitget #}
        <div class="exchange-group">
            <h2 class="exchange-title">Bitget</h2>
             <div class="space-y-3 sm:space-y-0 sm:space-x-3">
                {# Bitget 색상 미지정 -> 기존 보라색 계열 유지 #}
                <button onclick="startDownload('bitget', 'futures')" class="dl-button text-white bg-purple-500 hover:bg-purple-600">선물 (USDT)</button>
                 <button onclick="startDownload('bitget', 'spot_usdt')" class="dl-button spot-button">현물 (USDT)</button>
           </div>
        </div>

        {# 순서 변경: Upbit #}
        <div class="exchange-group">
            <h2 class="exchange-title">Upbit</h2>
             <div class="space-y-3 sm:space-y-0 sm:space-x-3">
                <button onclick="startDownload('upbit', 'spot_krw')" class="dl-button text-white" style="background-color: #013597;">현물 (KRW)</button>
                 {# Upbit USDT 현물 마켓이 있다면 추가 가능 #}
            </div>
        </div>

        {# 순서 변경: Bithumb #}
        <div class="exchange-group">
            <h2 class="exchange-title">Bithumb</h2>
             <div class="space-y-3 sm:space-y-0 sm:space-x-3">
                <button onclick="startDownload('bithumb', 'spot_krw')" class="dl-button text-black" style="background-color: #ff8200;">현물 (KRW)</button>
            </div>
        </div>

        <p id="status" class="text-sm text-gray-500 mt-6 h-5"></p> {# 상태 메시지 표시 영역 #}
    </div>

    <script>
        const statusP = document.getElementById('status');
        const allButtons = document.querySelectorAll('button.dl-button'); // 버튼 클래스로 선택

        // 다운로드 시작 함수 (거래소 ID, 마켓 타입 인자 추가)
        function startDownload(exchange, type) {
            // 사용자 친화적인 이름 매핑 (선택 사항)
            const exchangeMap = {'binance': 'Binance', 'bybit': 'Bybit', 'bingx': 'BingX', 'gateio': 'Gate.io', 'bitget': 'Bitget', 'upbit': 'Upbit', 'bithumb': 'Bithumb'};
            const typeMap = {'futures': '선물(USDT)', 'spot_usdt': '현물(USDT)', 'spot_krw': '현물(KRW)'};
            let exchangeNameKr = exchangeMap[exchange] || exchange.toUpperCase();
            let typeNameKr = typeMap[type] || type;

            statusP.textContent = `${exchangeNameKr} ${typeNameKr} 목록 생성 및 다운로드 준비 중...`;

            // 모든 버튼 비활성화
            allButtons.forEach(button => {
                button.disabled = true;
                // Tailwind 대신 opacity 직접 조절
                button.style.opacity = '0.5';
                button.style.cursor = 'not-allowed';
            });

            // '/download' 엔드포인트에 exchange와 type 파라미터 추가하여 요청
            window.location.href = `/download?exchange=${exchange}&type=${type}`;

            // 다운로드 시작 후 버튼 상태 복구 (시간 조절 필요)
            setTimeout(() => {
                statusP.textContent = `${exchangeNameKr} ${typeNameKr} 다운로드가 시작됩니다.`;
                 // 모든 버튼 활성화
                allButtons.forEach(button => {
                    button.disabled = false;
                     button.style.opacity = '1';
                    button.style.cursor = 'pointer';
                });
                setTimeout(() => { statusP.textContent = ''; }, 3000);
            }, 2500); // 시간 약간 더 늘림 (ccxt 로드가 더 걸릴 수 있음)
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

# 다운로드 엔드포인트 (exchange와 type 파라미터 사용)
@app.route('/download')
def download_symbols():
    """ 요청된 거래소와 마켓 타입의 심볼 목록을 생성하고 파일로 다운로드합니다. """
    exchange_id = request.args.get('exchange', '').lower()
    market_type = request.args.get('type', '').lower() # 예: 'futures', 'spot_usdt', 'spot_krw'

    # 파라미터 유효성 검사 (Gate.io 추가)
    supported_exchanges = ['binance', 'bybit', 'bingx', 'gateio', 'bitget', 'upbit', 'bithumb']
    supported_types = ['futures', 'spot_usdt', 'spot_krw']
    if exchange_id not in supported_exchanges or market_type not in supported_types:
        return "지원하지 않는 거래소 또는 마켓 타입입니다.", 400

    # 파일 이름에 사용할 기본 정보 설정
    quote_currency_for_filename = "USDT" # 기본값
    market_type_for_filename = market_type.split('_')[0] # 'futures' or 'spot'

    if market_type == 'spot_krw':
        quote_currency_for_filename = "KRW"
    # 선물(futures) 또는 USDT 현물(spot_usdt)은 USDT 사용
    elif market_type == 'futures' or market_type == 'spot_usdt':
         quote_currency_for_filename = "USDT"

    # 파일 이름 조합 (예: binance_futures_usdt_yymmdd.txt)
    base_filename_part = f"{exchange_id}_{market_type_for_filename}_{quote_currency_for_filename.lower()}"

    try:
        # 1. 통합 함수 호출하여 데이터 처리
        formatted_list = get_symbols_ccxt(exchange_id, market_type)

        if not formatted_list:
            return f"{exchange_id.upper()} ({market_type}) 에서 처리할 심볼을 찾지 못했거나 오류 발생.", 404

        # 2. 파일 이름 생성
        today_date = datetime.date.today()
        date_str = today_date.strftime("%y%m%d")
        final_filename = f"{base_filename_part}_{date_str}.txt"

        # 3. 파일 내용 생성 (정렬된 리스트 사용)
        output_string = ",".join(formatted_list) # get_symbols_ccxt에서 이미 정렬됨

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

    # ccxt 오류 및 기타 오류 처리
    except requests.exceptions.RequestException as e: # ccxt 오류도 이걸로 잡힘
        print(f"{exchange_id.upper()} ({market_type}) 요청 오류: {e}")
        return f"{exchange_id.upper()} ({market_type}) 정보 로드 중 오류 발생: {e}", 500
    except ValueError as e: # 지원하지 않는 거래소 ID 등
         print(f"값 오류: {e}")
         return str(e), 400
    except Exception as e:
        print(f"{exchange_id.upper()} ({market_type}) 서버 내부 오류: {e}")
        return f"{exchange_id.upper()} ({market_type}) 심볼 목록 생성 중 서버 내부 오류 발생: {e}", 500

# --- 서버 실행 ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

