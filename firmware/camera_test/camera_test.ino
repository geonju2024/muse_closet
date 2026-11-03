#include <Arduino.h>
#include "esp_camera.h"
// Seeed XIAO ESP32S3 Sense (OV3660) - Arduino ESP32 core 2.0.x
void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.printf("PSRAM found: %s, size: %u bytes\n",
                psramFound() ? "YES" : "NO", ESP.getPsramSize());

  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = 15; c.pin_d1 = 17; c.pin_d2 = 18; c.pin_d3 = 16;
  c.pin_d4 = 14; c.pin_d5 = 12; c.pin_d6 = 11; c.pin_d7 = 48;
  c.pin_xclk = 10; c.pin_pclk = 13; c.pin_vsync = 38; c.pin_href = 47;
  c.pin_sscb_sda = 40; c.pin_sscb_scl = 39;
  c.pin_pwdn = -1; c.pin_reset = -1;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = FRAMESIZE_QVGA;  // 320x240
  c.jpeg_quality = 12;
  c.fb_count = 1;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_WHEN_EMPTY;

  if (!psramFound()) {
    Serial.println("ERROR: PSRAM disabled. Enable OPI PSRAM in board menu.");
    return;
  }
  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    Serial.printf("Camera initialization failed: 0x%x\n", err);
    return;
  }
  sensor_t *s = esp_camera_sensor_get();
  if (s) Serial.printf("Camera PID: 0x%04x\n", s->id.PID);
  Serial.println("Camera initialized");
}

void loop() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Capture failed");
  } else {
    Serial.printf("Captured %ux%u JPEG, %u bytes\n",
                  fb->width, fb->height, (unsigned int)fb->len);
    esp_camera_fb_return(fb);
  }
  delay(3000);
}
