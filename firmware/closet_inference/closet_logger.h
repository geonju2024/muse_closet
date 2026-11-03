// MUSE Closet Vision - Wi-Fi + DB 로그 전송 (firmware/wifi_logger_example.h 기반)
#pragma once
#include <WiFi.h>
#include <HTTPClient.h>

// secrets.h(.gitignore)가 없으면(예: CI) 자리표시 값으로 컴파일만 되도록 함
#if __has_include("secrets.h")
#include "secrets.h"
#else
#warning "secrets.h not found - using placeholder values"
#define WIFI_SSID "YOUR_2_4GHZ_WIFI"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define API_URL "http://192.168.0.10:8000/api/predictions"
#endif

#ifndef DEVICE_ID
#define DEVICE_ID "xiao-esp32s3-01"
#endif
#ifndef MODEL_VERSION
#define MODEL_VERSION "ei-1.0.1"
#endif

void closetConnectWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 12000) {
    delay(300);
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("WiFi connected, IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("WiFi failed: SSID/비밀번호, 2.4GHz 여부 확인");
  }
}

// 성공 시 DB id(>0), 실패 시 HTTP 상태코드(음수=연결 실패) 또는 0 반환
int closetSendPrediction(const char *category, float confidence, uint32_t inferenceMs) {
  if (WiFi.status() != WL_CONNECTED) {
    closetConnectWifi();
    if (WiFi.status() != WL_CONNECTED) return -100;
  }
  HTTPClient http;
  http.begin(API_URL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(2500);
  String payload = String("{\"device_id\":\"") + DEVICE_ID + "\","
                   "\"category\":\"" + category + "\","
                   "\"confidence\":" + String(confidence, 4) + ","
                   "\"inference_ms\":" + String(inferenceMs) + ","
                   "\"model_version\":\"" + MODEL_VERSION + "\"}";
  int statusCode = http.POST(payload);
  int dbId = 0;
  if (statusCode == 201) {
    String body = http.getString();  // {"id":N,"created_at":...,"saved":true}
    int p = body.indexOf("\"id\":");
    if (p >= 0) dbId = body.substring(p + 5).toInt();
  }
  Serial.printf("DB upload status: %d%s\n", statusCode,
                statusCode == 201 ? "" : (statusCode < 0 ? " (연결 실패: API_URL IP·방화벽·서버 확인)" : " (서버 거부)"));
  http.end();
  return statusCode == 201 ? dbId : statusCode;
}
