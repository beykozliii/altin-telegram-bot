
import os
import json
import requests
import pandas as pd
import yfinance as yf

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
STATE_FILE = "state.json"

def renk(diff, onceki):
    if pd.isna(onceki):
        return "DIGER"
    if diff >= 0:
        return "MAVI" if diff >= onceki else "ACIK_MAVI"
    return "KOYU_KIRMIZI" if diff <= onceki else "KIRMIZI"

def telegram(mesaj):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    response = requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": mesaj},
        timeout=20
    )
    response.raise_for_status()

def main():
    df = yf.download(
        "XAUUSD=X",
        period="5d",
        interval="15m",
        progress=False,
        auto_adjust=False
    )

    if df.empty:
        raise RuntimeError("Altın verisi alınamadı.")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.index = pd.to_datetime(df.index, utc=True)
    df = df[~df.index.duplicated(keep="last")].sort_index()

    ohlc4 = (df["Open"] + df["High"] +
             df["Low"] + df["Close"]) / 4

    fark = (
        ohlc4.ewm(span=10, adjust=False).mean()
        - ohlc4.ewm(span=18, adjust=False).mean()
    )

    renkler = [
        renk(fark.iloc[i], fark.iloc[i - 1])
        for i in range(len(fark))
    ]
    df["renk"] = renkler

    simdi = pd.Timestamp.now(tz="UTC")
    tamamlanan = df[
        df.index + pd.Timedelta(minutes=15) <= simdi
    ]

    if len(tamamlanan) < 20:
        raise RuntimeError("Yeterli kapanmış mum yok.")

    son = tamamlanan.iloc[-1]
    onceki = tamamlanan.iloc[-2]
    mum_zamani = tamamlanan.index[-1].isoformat()

    onceki_durum = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            onceki_durum = json.load(f)

    hedef = son["renk"]
    onceki_renk = onceki["renk"]

    if hedef not in ("MAVI", "KOYU_KIRMIZI"):
        print("Yeni sinyal yok.")
        return

    if hedef == onceki_renk:
        print("Yeni renk geçişi yok.")
        return

    if onceki_durum.get("son_sinyal_mumu") == mum_zamani:
        print("Bu mum için sinyal zaten gönderilmiş.")
        return

    yon = "MAVİ SİNYAL" if hedef == "MAVI" else "KOYU KIRMIZI SİNYAL"
    fiyat = float(son["Close"])

    mesaj = (
        f"DynaRange - {yon}\n"
        f"Enstrüman: XAU/USD (Yahoo Finance)\n"
        f"Zaman dilimi: 15 dakika\n"
        f"Kapanış: {fiyat:.2f}\n"
        f"Mum zamanı: {mum_zamani}\n"
        f"Bu mesaj işlem açmaz; yalnızca sinyaldir."
    )

    telegram(mesaj)

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"son_sinyal_mumu": mum_zamani},
            f,
            ensure_ascii=False,
            indent=2
        )

    print("Telegram sinyali gönderildi:", yon)

if __name__ == "__main__":
    main()
