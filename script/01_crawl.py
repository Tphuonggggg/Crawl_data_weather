# crawl_openmeteo_vietnam_2026_34tinh.py
# Tọa độ = centroid trung bình của tất cả tỉnh được gộp
# → Bao quát toàn bộ vùng địa lý, không thiên lệch về trụ sở

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import json
import time
import os
import math
from datetime import date, timedelta

os.makedirs("data/raw/openmeteo_2026", exist_ok=True)
PROGRESS_PATH = "data/raw/openmeteo_2026/crawl_progress.json"

POINT_SPAN_KM = 25
POINT_COUNT = 5
REQUEST_DELAY = 5.0
PROVINCE_DELAY = 5.0
RATE_LIMIT_WAIT = 5

LARGE_PROVINCES = {
    "Quảng Ninh",
    "Quảng Trị",
    "Lào Cai",
    "Điện Biên",
    "Tuyên Quang",
    "Cao Bằng",
    "Lai Châu",
    "Khánh Hòa",
    "An Giang",
    "Đồng Tháp",
    "Cà Mau",
}

VERY_LARGE_PROVINCES = {
    "Nghệ An",
    "Thanh Hóa",
    "Sơn La",
    "Gia Lai",
    "Lâm Đồng",
    "Đắk Lắk",
}

RETRY_STRATEGY = Retry(
    total=2,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["GET"],
    raise_on_status=False,
)
SESSION = requests.Session()
SESSION.mount("https://", HTTPAdapter(max_retries=RETRY_STRATEGY))
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})

TODAY = date.today()
START_DATE_RAW = TODAY - timedelta(days=180)
EXPECTED_DAYS = (TODAY - START_DATE_RAW).days + 1

START_DATE = START_DATE_RAW.strftime("%Y-%m-%d")
END_DATE = TODAY.strftime("%Y-%m-%d")

# ── 34 tỉnh/thành sau sáp nhập — danh sách tọa độ đại diện ────────
# Mỗi tỉnh có thể dùng nhiều điểm quan trắc trong tỉnh, sau đó lấy trung bình theo ngày.
PROVINCES = {
    "Tuyên Quang": (22.3235, 105.1009),
    "Lào Cai": (22.0954, 104.4233),
    "Thái Nguyên": (21.8706, 105.8380),
    "Phú Thọ": (21.1958, 105.3701),
    "Bắc Ninh": (21.2017, 106.1543),
    "Hưng Yên": (20.5482, 106.1955),
    "Hải Phòng": (20.8928, 106.5095),
    "Ninh Bình": (20.4191, 106.0219),
    "Quảng Trị": (17.1046, 106.8916),
    "Đà Nẵng": (15.7969, 108.1106),
    "Quảng Ngãi": (14.7379, 108.4018),
    "Gia Lai": (13.8799, 108.6119),
    "Khánh Hòa": (11.9564, 109.0298),
    "Lâm Đồng": (11.6785, 108.0758),
    "Đắk Lắk": (12.8991, 108.6653),
    "Hồ Chí Minh": (10.8967, 106.7832),
    "Đồng Nai": (11.4099, 106.9455),
    "Tây Ninh": (11.0154, 106.1765),
    "Cần Thơ": (9.8019, 105.7894),
    "Vĩnh Long": (10.1436, 106.2249),
    "Đồng Tháp": (10.4713, 106.0152),
    "Cà Mau": (9.2355, 105.4358),
    "An Giang": (10.2670, 105.1034),
    "Hà Nội": (21.0285, 105.8542),
    "Huế": (16.4637, 107.5909),
    "Lai Châu": (22.3964, 103.4580),
    "Điện Biên": (21.3860, 103.0230),
    "Sơn La": (21.3256, 103.9188),
    "Lạng Sơn": (21.8537, 106.7615),
    "Quảng Ninh": (21.0064, 107.2925),
    "Thanh Hóa": (19.8074, 105.7764),
    "Nghệ An": (18.6796, 105.6813),
    "Hà Tĩnh": (18.3560, 105.9000),
    "Cao Bằng": (22.6657, 106.2522),
}


def make_sample_points(lat, lon, span_km=POINT_SPAN_KM, count=POINT_COUNT):
    if count <= 1:
        return [(lat, lon)]

    # Sample one center point plus an evenly spaced ring around it.
    dlat = span_km / 110.574
    dlon = span_km / (111.320 * max(abs(math.cos(math.radians(lat))), 0.1))

    points = [(lat, lon)]
    ring_count = count - 1
    for index in range(ring_count):
        angle = (2 * math.pi * index) / ring_count
        offset_lat = math.sin(angle) * dlat
        offset_lon = math.cos(angle) * dlon
        points.append((lat + offset_lat, lon + offset_lon))

    return points


def province_sample_count(name):
    if name in VERY_LARGE_PROVINCES:
        return 11
    if name in LARGE_PROVINCES:
        return 9
    return POINT_COUNT


def load_complete_province_file(fpath):
    if not os.path.exists(fpath):
        return None

    try:
        df = pd.read_csv(fpath, parse_dates=["date", "sunrise", "sunset"])
    except Exception:
        return None

    required_columns = {
        "province", "region", "date", "weather_code", "temperature_2m_mean",
        "temperature_2m_max", "temperature_2m_min", "apparent_temperature_mean",
        "apparent_temperature_max", "apparent_temperature_min", "sunrise", "sunset",
        "uv_index_max", "uv_index_clear_sky_max", "precipitation_sum", "rain_sum",
        "showers_sum", "precipitation_hours", "precipitation_probability_max",
        "relative_humidity_2m_mean", "wind_speed_10m_max", "wind_gusts_10m_max",
        "wind_direction_10m_dominant", "shortwave_radiation_sum", "pressure_msl_mean",
        "cloud_cover_mean", "dew_point_2m_mean", "snowfall_sum",
        "et0_fao_evapotranspiration", "latitude", "longitude", "sunshine_hours",
        "daylight_hours", "month", "week", "season"
    }

    if not required_columns.issubset(df.columns):
        return None

    if len(df) != EXPECTED_DAYS:
        return None

    if df["date"].nunique() != EXPECTED_DAYS:
        return None

    return df


def load_completed_provinces():
    if not os.path.exists(PROGRESS_PATH):
        return set()

    try:
        with open(PROGRESS_PATH, "r", encoding="utf-8") as handle:
            progress = json.load(handle)
    except Exception:
        return set()

    if progress.get("start_date") != START_DATE or progress.get("end_date") != END_DATE:
        return set()

    completed = progress.get("completed_provinces", [])
    if not isinstance(completed, list):
        return set()

    return set(completed)


def save_completed_provinces(completed_provinces):
    payload = {
        "start_date": START_DATE,
        "end_date": END_DATE,
        "completed_provinces": sorted(completed_provinces),
    }

    temp_path = f"{PROGRESS_PATH}.tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    os.replace(temp_path, PROGRESS_PATH)

REGION_MAP = {
    "Hà Nội":      "Đồng bằng sông Hồng",
    "Hưng Yên":    "Đồng bằng sông Hồng",
    "Ninh Bình":   "Đồng bằng sông Hồng",
    "Hải Phòng":   "Đồng bằng sông Hồng",
    "Bắc Ninh":    "Đồng bằng sông Hồng",
    "Cao Bằng":    "Trung du miền núi Bắc Bộ",
    "Lạng Sơn":    "Trung du miền núi Bắc Bộ",
    "Quảng Ninh":  "Trung du miền núi Bắc Bộ",
    "Thái Nguyên": "Trung du miền núi Bắc Bộ",
    "Tuyên Quang": "Trung du miền núi Bắc Bộ",
    "Phú Thọ":     "Trung du miền núi Bắc Bộ",
    "Lào Cai":     "Trung du miền núi Bắc Bộ",
    "Lai Châu":    "Trung du miền núi Bắc Bộ",
    "Điện Biên":   "Trung du miền núi Bắc Bộ",
    "Sơn La":      "Trung du miền núi Bắc Bộ",
    "Thanh Hóa":   "Bắc Trung Bộ",
    "Nghệ An":     "Bắc Trung Bộ",
    "Hà Tĩnh":     "Bắc Trung Bộ",
    "Quảng Trị":   "Bắc Trung Bộ",
    "Huế":         "Bắc Trung Bộ",
    "Đà Nẵng":     "Duyên hải Nam Trung Bộ",
    "Quảng Ngãi":  "Duyên hải Nam Trung Bộ",
    "Gia Lai":     "Tây Nguyên",
    "Khánh Hòa":   "Duyên hải Nam Trung Bộ",
    "Đắk Lắk":     "Tây Nguyên",
    "Lâm Đồng":    "Tây Nguyên",
    "Hồ Chí Minh": "Đông Nam Bộ",
    "Đồng Nai":    "Đông Nam Bộ",
    "Tây Ninh":    "Đông Nam Bộ",
    "An Giang":    "Đồng bằng sông Cửu Long",
    "Đồng Tháp":   "Đồng bằng sông Cửu Long",
    "Vĩnh Long":   "Đồng bằng sông Cửu Long",
    "Cần Thơ":     "Đồng bằng sông Cửu Long",
    "Cà Mau":      "Đồng bằng sông Cửu Long",
}

DAILY_VARS = [
    "weather_code",

    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",

    "apparent_temperature_mean",
    "apparent_temperature_max",
    "apparent_temperature_min",

    "sunrise",
    "sunset",
    "daylight_duration",
    "sunshine_duration",

    # UV index for health/risk assessment
    "uv_index_max",
    "uv_index_clear_sky_max",

    "precipitation_sum",
    "rain_sum",
    "showers_sum",
    "precipitation_hours",
    "precipitation_probability_max",

    "relative_humidity_2m_mean",

    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",

    "shortwave_radiation_sum",

    "pressure_msl_mean",

    "cloud_cover_mean",

    "dew_point_2m_mean",

    "snowfall_sum",

    "et0_fao_evapotranspiration"
]

def crawl_point(name, lat, lon):
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude":           lat,
        "longitude":          lon,
        "start_date":         START_DATE,
        "end_date":           END_DATE,
        "daily":              ",".join(DAILY_VARS),
        "timezone":           "Asia/Bangkok",
        "wind_speed_unit":    "kmh",
        "precipitation_unit": "mm",
        "temperature_unit":   "celsius",
    }

    data = None
    try:
        for attempt in range(3):
            try:
                print(f"      📡 Attempt {attempt + 1}/3...", end="", flush=True)
                resp = SESSION.get(
                    url,
                    params=params,
                    timeout=(5, 20),
                    allow_redirects=True,
                )

                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    wait = int(retry_after) if retry_after and retry_after.isdigit() else RATE_LIMIT_WAIT
                    wait = min(wait, 5)
                    print(f" ⏱️ Rate limited (429). Chờ {wait} giây...")
                    if attempt < 1:
                        time.sleep(wait)
                        print("      ⚠️  Bỏ điểm do rate limit và tiếp tục tỉnh tiếp theo.")
                        return None
                    print("      ⚠️  Rate limit vẫn còn sau lần retry cuối. Bỏ điểm này.")
                    return None

                resp.raise_for_status()
                data = resp.json()
                print(" ✓")
                break

            except (requests.exceptions.ConnectTimeout,
                    requests.exceptions.ReadTimeout,
                    requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.SSLError) as e:
                print(f" ⏱️ Request Error: {type(e).__name__}")
                if attempt == 2:
                    raise
                print("      ⏳ Chờ 10 giây trước khi retry...")
                time.sleep(10)

            except requests.exceptions.HTTPError as e:
                status = getattr(e.response, 'status_code', None)
                print(f" ✗ HTTPError {status}")
                if status == 429 and attempt < 2:
                    retry_after = e.response.headers.get("Retry-After")
                    wait = int(retry_after) if retry_after and retry_after.isdigit() else RATE_LIMIT_WAIT
                    print(f"      ⏳ Chờ {wait} giây trước khi retry...")
                    time.sleep(wait)
                    continue
                raise

            except requests.exceptions.RequestException as e:
                print(f" ✗ RequestException: {type(e).__name__}")
                if attempt == 2:
                    raise
                print("      ⏳ Chờ 10 giây trước khi retry...")
                time.sleep(10)

            except Exception as e:
                print(f" ✗ Error: {type(e).__name__}")
                if attempt == 2:
                    raise
                print("      ⏳ Chờ 10 giây trước khi retry...")
                time.sleep(10)

        if data is None or "daily" not in data:
            reason = data.get('reason', 'Không có dữ liệu') if data else 'Không có dữ liệu'
            print(f"  ⚠️  {name}: {reason}")
            return None

        df = pd.DataFrame(data["daily"])
        df.rename(columns={"time": "date"}, inplace=True)
        df["latitude"] = lat
        df["longitude"] = lon

        if "sunshine_duration" in df.columns:
            df["sunshine_hours"] = (
                df["sunshine_duration"] / 3600
            ).round(2)
            df.drop(columns=["sunshine_duration"], inplace=True)

        if "daylight_duration" in df.columns:
            df["daylight_hours"] = (
                df["daylight_duration"] / 3600
            ).round(2)
            df.drop(columns=["daylight_duration"], inplace=True)

        df["date"] = pd.to_datetime(df["date"])
        if "sunrise" in df.columns:
            df["sunrise"] = pd.to_datetime(df["sunrise"])
        if "sunset" in df.columns:
            df["sunset"] = pd.to_datetime(df["sunset"])

        df["month"] = df["date"].dt.month
        df["week"] = df["date"].dt.isocalendar().week.astype(int)
        df["season"] = df["month"].map({
            1:"Đông", 2:"Đông", 3:"Xuân", 4:"Xuân",
            5:"Xuân", 6:"Hè",   7:"Hè",   8:"Hè",
            9:"Thu", 10:"Thu", 11:"Thu",  12:"Đông"
        })

        return df

    except Exception as e:
        print(f"  ❌ {name}: {type(e).__name__} — {e}")
        return None


def aggregate_province(name, point_dfs):
    if not point_dfs:
        return None
    if len(point_dfs) == 1:
        df = point_dfs[0]
    else:
        df_all = pd.concat(point_dfs, ignore_index=True)
        numeric_cols = df_all.select_dtypes(include="number").columns.tolist()
        for col in ["weather_code", "wind_direction_10m_dominant"]:
            if col in numeric_cols:
                numeric_cols.remove(col)

        df = df_all.groupby("date")[numeric_cols].mean()

        if "weather_code" in df_all.columns:
            df["weather_code"] = df_all.groupby("date")["weather_code"].agg(
                lambda x: x.mode().iat[0] if not x.mode().empty else x.iloc[0]
            )

        if "wind_direction_10m_dominant" in df_all.columns:
            df["wind_direction_10m_dominant"] = df_all.groupby("date")["wind_direction_10m_dominant"].agg(
                lambda x: x.mode().iat[0] if not x.mode().empty else x.iloc[0]
            )

        for col in ["sunrise", "sunset"]:
            if col in df_all.columns:
                df[col] = pd.to_datetime(
                    df_all.groupby("date")[col]
                    .agg(lambda s: s.astype("int64").mean())
                )

        df = df.reset_index()

    df.insert(0, "province", name)
    df.insert(1, "region", REGION_MAP.get(name, "Khác"))
    df["month"] = df["date"].dt.month
    df["week"] = df["date"].dt.isocalendar().week.astype(int)
    df["season"] = df["month"].map({
        1:"Đông", 2:"Đông", 3:"Xuân", 4:"Xuân",
        5:"Xuân", 6:"Hè",   7:"Hè",   8:"Hè",
        9:"Thu", 10:"Thu", 11:"Thu",  12:"Đông"
    })

    return df


def crawl_province(name, points):
    dfs = []
    for lat, lon in points:
        point_df = crawl_point(name, lat, lon)
        if point_df is not None:
            dfs.append(point_df)
        time.sleep(REQUEST_DELAY)

    df = aggregate_province(name, dfs)
    if df is not None:
        print(f"  ✅ {name}: {len(df)} ngày | mưa TB {df['precipitation_sum'].mean():.1f}mm/ngày")
    return df

def crawl_all():
    all_dfs = []
    total   = len(PROVINCES)
    completed_provinces = load_completed_provinces()

    print("=" * 65)
    print("  🌏 KTTV Việt Nam 2026 — 34 tỉnh/thành sau sáp nhập")
    print("  📍 Tọa độ: centroid trung bình toàn vùng sáp nhập")
    print(
        f"  📅 {START_DATE} → {END_DATE}"
        f" | {len(DAILY_VARS)} biến"
    )
    print("=" * 65)

    if completed_provinces:
        print(f"  🔁 Resume: đã ghi nhận {len(completed_provinces)} tỉnh/thành hoàn tất từ lần chạy trước")

    for i, (name, coords) in enumerate(PROVINCES.items(), 1):
        if isinstance(coords, tuple):
            points = make_sample_points(
                coords[0],
                coords[1],
                count=province_sample_count(name),
            )
        elif isinstance(coords, list) and len(coords) == 1:
            points = make_sample_points(
                coords[0][0],
                coords[0][1],
                count=province_sample_count(name),
            )
        else:
            points = coords

        if len(points) == 1:
            points = make_sample_points(
                points[0][0],
                points[0][1],
                count=province_sample_count(name),
            )

        print(f"\n[{i:02d}/{total}] {name} — {len(points)} điểm trong tỉnh")
        print(f"         Dữ liệu được lấy từ nhiều điểm quanh centroid và lấy trung bình")

        safe  = name.replace(" ", "_").replace("/", "-").replace(".", "")
        fpath = (
            f"data/raw/openmeteo_2026/"
            f"{safe}_{START_DATE}_{END_DATE}.csv"
        )

        if name in completed_provinces:
            df = load_complete_province_file(fpath)
            if df is not None:
                print("  ⏭️  Đã hoàn tất từ lần chạy trước, bỏ qua crawl lại")
                all_dfs.append(df)
                time.sleep(PROVINCE_DELAY)
                continue

            completed_provinces.discard(name)

        df = load_complete_province_file(fpath)
        if df is not None:
            print(f"  ⏭️  Đã có file hoàn chỉnh ({len(df)} dòng)")
            completed_provinces.add(name)
            save_completed_provinces(completed_provinces)
        else:
            if os.path.exists(fpath):
                print("  ♻️  File cũ chưa đủ hoặc lỗi, sẽ crawl lại tỉnh này")

            df = crawl_province(name, points)
            if df is not None:
                df.to_csv(fpath, index=False, encoding="utf-8-sig")
                completed_provinces.add(name)
                save_completed_provinces(completed_provinces)

        if df is not None:
            all_dfs.append(df)

        time.sleep(PROVINCE_DELAY)

    print("\n" + "=" * 65)
    print("  📦 Đang gộp dữ liệu toàn quốc...")

    if not all_dfs:
        print("  ⚠️  Không có dữ liệu hợp lệ nào để gộp. Kiểm tra lại kết nối/API hoặc file đầu vào.")
        return

    df_final = pd.concat(all_dfs, ignore_index=True)
    df_final = df_final.sort_values(["date", "province"]).reset_index(drop=True)

    output = (
        f"data/raw/"
        f"vietnam_kttv_34tinh_"
        f"{START_DATE}_{END_DATE}.csv"
    )
    df_final.to_csv(output, index=False, encoding="utf-8-sig")

    missing_rate = (
        df_final.isnull().mean() * 100
    ).round(2)

    print("\n📌 Tỷ lệ thiếu dữ liệu (%)")
    print(
        missing_rate[
            missing_rate > 0
        ].sort_values(ascending=False)
    )

    print(f"""
  ✅ HOÀN TẤT!
  {"─" * 50}
  📄 File      : {output}
  📊 Số dòng   : {len(df_final):,}
  🏙️  Số tỉnh   : {df_final['province'].nunique()} tỉnh/thành
  📅 Thời gian : {df_final['date'].min().date()} → {df_final['date'].max().date()}
  📈 Số cột    : {len(df_final.columns)}
  {"─" * 50}
    """)

    for vung, grp in df_final.groupby("region"):
        print(f"  • {vung}: {grp['province'].nunique()} tỉnh")

if __name__ == "__main__":
    try:
        crawl_all()
    except KeyboardInterrupt:
        print("\n  ⏸️  Đã dừng thủ công. Lần chạy sau sẽ tiếp tục từ các tỉnh đã lưu checkpoint.")