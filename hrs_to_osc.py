# Copyright (c) 2026 takuu-o
# Released under the MIT License.

import asyncio
import json
import struct
from pathlib import Path

from bleak import BleakClient, BleakScanner
from pythonosc import udp_client


# Heart Rate Service UUIDs
HEART_RATE_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HEART_RATE_SERVICE_UUID_SHORT = "180d"
HEART_RATE_MEASUREMENT_UUID_SHORT = "2a37"

# 設定値
CONFIG = {
    "osc": {
        "server_ip": "127.0.0.1",
        "server_port": 9000,
        "address": "/avatar/parameters/",
    },
    "connection": {
        "timeout": 20.0,
        "max_retries": 5,
        "retry_delay": 3,
        "scan_timeout": 10,
        "scan_retry_interval": 5,
        "maintain_interval": 1,
    },
}


def merge_config(default_config: dict, user_config: dict) -> dict:
    result = default_config.copy()
    for key, value in user_config.items():
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = value
    return result


def initialize_config(config_file: str = "config.json") -> dict:
    """
    設定ファイル読み込み
    """
    global CONFIG

    try:
        config_path = Path(config_file)
        if not config_path.exists():
            print(f"{config_file} が見つかりません。")

        with open(config_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)

        # デフォルト値とユーザー設定を深くマージ
        CONFIG = merge_config(CONFIG, user_config)

    except json.JSONDecodeError:
        print(f"{config_file} のJSONフォーマットが不正です。")
    except Exception as e:
        print(f"設定ファイルの読み込みに失敗しました: {e}")


async def scan_and_connect():
    """心拍センサーをスキャンして接続"""

    print("心拍センサーをスキャン中...")

    devices = await BleakScanner.discover(
        return_adv=True, timeout=CONFIG["connection"]["scan_timeout"]
    )

    for device, adv_data in devices.values():
        if hasattr(adv_data, "service_uuids"):
            uuids = adv_data.service_uuids
            # Heart Rate Serviceを持つデバイスを探す
            if (
                HEART_RATE_SERVICE_UUID in uuids
                or HEART_RATE_SERVICE_UUID_SHORT in uuids
            ):
                print(
                    f"\n✓ 心拍センサーを検出: {getattr(device, 'name', '不明なデバイス')}"
                )
                print(f"  アドレス: {device.address}")
                return device.address

    print("心拍センサーが見つかりませんでした")
    return None


def parse_heart_rate(data):
    """心拍数データを解析"""

    if len(data) < 2:
        return None

    # フラグを確認
    flags = data[0]

    # 心拍数値のフォーマットをチェック
    if flags & 0x01:  # 16-bit
        if len(data) >= 3:
            return struct.unpack("<H", data[1:3])[0]
    else:  # 8-bit
        return data[1]

    return None


def send_osc(osc_client, osc_address: str, send_list):
    """OSC送信"""

    try:
        # 心拍数を送信

        for data in send_list:
            osc_client.send_message(osc_address + data["address"], data["value"])
            print(f"OSC送信: {data['address']} -> {data['value']}")

    except Exception as e:
        print(f"OSC送信エラー: {e}")


def create_notification_handler(osc_client, osc_address: str):
    """通知ハンドラーをクロージャーで生成"""

    def notification_handler(characteristic, data):
        """通知ハンドラー"""
        heart_rate = parse_heart_rate(data)
        if heart_rate:
            print(f"心拍数: {heart_rate} BPM")
            # 正規化された値を送信（0.0-1.0にマッピング）
            # 0.2秒 + 0.2秒 x [calculated_hr] = 指定周期 の計算
            HR_CONST = 0.2  # 心拍数定数
            HR_FLEX = 0.2  # 心拍数フレックス

            calculated_hr = 1 / (1 / HR_CONST * (60 / heart_rate - HR_FLEX))
            normalized_hr = max(0.0, min(1.0, calculated_hr))

            # OSCで心拍データを送信
            send_osc(
                osc_client,
                osc_address,
                [
                    {
                        "address": "heartbeat_value",
                        "value": heart_rate,
                    },
                    {
                        "address": "heartbeat_waittime",
                        "value": normalized_hr,
                    },
                ],
            )

    return notification_handler


async def main():
    """メイン処理"""
    initialize_config()

    print(f"OSC設定: {CONFIG['osc']['server_ip']}:{CONFIG['osc']['server_port']}")
    print(f"OSCアドレス: {CONFIG['osc']['address']}")
    print("-" * 40)

    device_address = None
    retry_count = 0

    # 通知ハンドラーを生成
    osc_client = udp_client.SimpleUDPClient(
        CONFIG["osc"]["server_ip"], CONFIG["osc"]["server_port"]
    )
    notification_handler = create_notification_handler(
        osc_client, CONFIG["osc"]["address"]
    )

    while True:
        try:
            # デバイスをスキャン（まだアドレスがない場合）
            if not device_address:
                device_address = await scan_and_connect()
                if not device_address:
                    print(
                        f"{CONFIG['connection']['scan_retry_interval']}秒後に再スキャンします..."
                    )
                    await asyncio.sleep(CONFIG["connection"]["scan_retry_interval"])
                    continue

            print(
                f"\nデバイスに接続中: {device_address} (試行 {retry_count + 1}/{CONFIG['connection']['max_retries']})"
            )

            # タイムアウトと接続監視を追加
            async with BleakClient(
                device_address,
                timeout=CONFIG["connection"]["timeout"],  # 接続タイムアウト
                disconnected_callback=lambda client: print("デバイスが切断されました"),
            ) as client:
                print("接続成功")
                retry_count = 0  # 接続成功したらリトライカウントをリセット

                # 心拍測定の通知を開始
                await client.start_notify(
                    HEART_RATE_MEASUREMENT_UUID_SHORT, notification_handler
                )
                print("心拍モニタリング開始 (Ctrl+C で停止)")
                print("OSC送信開始")

                # 接続維持ループ
                while client.is_connected:
                    await asyncio.sleep(CONFIG["connection"]["maintain_interval"])

                print("接続が失われました。再接続します...")

        except KeyboardInterrupt:
            print("\nモニタリング停止")
            break
        except asyncio.TimeoutError:
            print("接続タイムアウト。再試行します...")
            retry_count += 1
        except Exception as e:
            print(f"エラー: {e}")
            retry_count += 1

        # 最大リトライ回数に達した場合
        if retry_count >= CONFIG["connection"]["max_retries"]:
            print(
                f"{CONFIG['connection']['max_retries']}回の接続失敗。デバイスアドレスをリセットして再スキャンします..."
            )
            device_address = None
            retry_count = 0
            await asyncio.sleep(CONFIG["connection"]["retry_delay"])
        else:
            # 再接続前に少し待機
            print(f"{CONFIG['connection']['retry_delay']}秒後に再接続を試みます...")
            await asyncio.sleep(CONFIG["connection"]["retry_delay"])


if __name__ == "__main__":
    asyncio.run(main())
