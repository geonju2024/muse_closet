// 사용법: Edge Impulse esp32_camera 예제의 #include 뒤에 추가하여 사용
// 이 파일은 단독 컴파일하는 스케치가 아닙니다.
#include <WiFi.h>
#include <HTTPClient.h>
#include "secrets.h"  // 사용자가 로컬에서 생성; Git에는 커밋하지 않기

void closetConnectWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 12000) {
    delay(300);
  }
  Serial.println(WiFi.status() == WL_CONNECTED ? "WiFi connected" : "WiFi failed");
}

void closetSendPrediction(const String &category, float confidence, uint32_t inferenceMs) {
  if (WiFi.status() != WL_CONNECTED) {
    closetConnectWifi();
    if (WiFi.status() != WL_CONNECTED) return;
  }
  HTTPClient http;
  http.begin(API_URL); // 예: http://192.168.0.10:8000/api/predictions
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(2500);
  String payload = "{\"device_id\":\"xiao-esp32s3-01\","
                   "\"category\":\"" + category + "\","
                   "\"confidence\":" + String(confidence, 4) + ","
                   "\"inference_ms\":" + String(inferenceMs) + ","
                   "\"model_version\":\"v1\"}";
  int statusCode = http.POST(payload);
  Serial.printf("DB upload status: %d\n", statusCode);
  http.end();
}

// Edge Impulse run_classifier() 성공 후 추가할 코드 예시:
// int bestIndex = 0;
// for (int i = 1; i < EI_CLASSIFIER_LABEL_COUNT; ++i) {
//   if (result.classification[i].value > result.classification[bestIndex].value) bestIndex = i;
// }
// String label = result.classification[bestIndex].label;
// closetSendPrediction(label, result.classification[bestIndex].value,
//                    result.timing.dsp + result.timing.classification);
// 'setup()' 끝부분에는 closetConnectWifi()를 호출하세요.
