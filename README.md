# BLE Heart Rate → OSC Bridge (Reference Implementation)

BLE対応心拍計から心拍数を取得し、OSC経由で送信するPythonコードです。
本リポジトリは，心拍OSC連携の一例として公開しています。  
改変・再利用・発展を歓迎します。

---

## Overview

- BLE Heart Rate Service (0x180D) に対応
- 心拍数を取得しOSCで送信
- VRChatでのOSC連携を想定
- MIT License

---

## Features

- 心拍数（BPM）をそのまま送信
- ギミック向けの正規化値の計算例を含む
- 設定ファイル（config.json）によるカスタマイズ

---

## Getting Started

### 1. Python環境

Python 3.11 以上で検証しています。

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Rum

```bash
python hrs_to_osc.py
```

## OSC Parameters

デフォルトで以下のOSCパラメータを送信します：

OSC Address                     | Type  | Description
--------------------------------|-------|----------------------------
/avatar/parameters/taklabs/heartbeat_value     | Int   | Heart Rate in BPM
/avatar/parameters/taklabs/heartbeat_waittime  | Float | Normalized value (0.0-1.0)

---

## Configuration

`config.json` で以下を設定できます：

- OSC送信先IP
- ポート番号
- 再接続設定
- スキャン間隔など

---

## Related Project

本ツールは、以下のVRChat向け心音ギミックのために制作されました：

Booth:  
https://taklabs.booth.pm/items/8001371

※ 本ツールは単体で利用可能です。

---

## License

MIT License

Copyright (c) 2026 takuu-o

---

## Notes

- 心拍データは保存しません（リアルタイム送信のみ）
- BLE動作はOS・デバイスに依存します
- 動作確認環境：
  - OS: Windows 11，
  - 心拍計: Coospo HW706

---
