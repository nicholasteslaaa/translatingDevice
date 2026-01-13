#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <driver/i2s.h>

Preferences prefs;

// --- SETTINGS ---
String availableWifi[5];
int availableWifiSize = sizeof(availableWifi) / sizeof(availableWifi[0]);

const char* serverUrl = "http://192.168.1.4:8000/upload";

#define RECORD_BUTTON1 19
#define RECORD_BUTTON2 17
#define ADC_INPUT_PIN 1
#define SAMPLE_RATE 16000
#define RECORD_TIME 10

#define UP_BUTTON 12
#define DOWN_BUTTON 10
#define SELECT_BUTTON 13
#define LEFT_BUTTON 11
#define RIGHT_BUTTON 46

// --- GLOBALS ---
int SCREEN_WIDTH = 128;
int SCREEN_HEIGHT = 64;
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
String languageOption[] = { "english", "japanese" };
String sourceLanguage = languageOption[0];
String outputLanguage = languageOption[1];

// Audio Buffer
size_t maxSamples = SAMPLE_RATE * RECORD_TIME;
int16_t* fullBuffer = nullptr;
size_t samplesRecorded = 0;
unsigned long nextSampleTime = 0;
const unsigned long microsecondsPerSample = 1000000 / SAMPLE_RATE;

// UI State
float recordTimer = RECORD_TIME;
unsigned long lastTime = 0;
bool send_API_trigger = false;
int pressedButton = 0;

// -- FLASH ACCESS ---
// save file setting
const char* filename = "/data.json";
void addData(String key, String value) {
  prefs.begin("settings", false); // "settings" is the namespace
  prefs.putString(key.c_str(), value);
  prefs.end();
  Serial.println("Saved " + key + " to NVM");
}

String getData(String key) {
  prefs.begin("settings", true); // true = read-only mode
  String value = prefs.getString(key.c_str(), ""); // "" is the default if not found
  prefs.end();
  return value;
}

// --- HELPERS ---
int getXMid(String msg, int textSize = 1) {
  return (SCREEN_WIDTH - (msg.length() * 6 * textSize)) / 2;
}

int getXRight(String msg, int textSize = 1) {
  return SCREEN_WIDTH - (msg.length() * 6 * textSize);
}
int getYMid(int textSize = 1) {
  // A character is 8 pixels tall per textSize unit
  int textHeight = 8 * textSize;
  return (SCREEN_HEIGHT - textHeight) / 2;
}

int getYBottom(int textSize = 1) {
  int textHeight = 8 * textSize;
  return SCREEN_HEIGHT - textHeight;
}

void updateScreen(String msg, int textSize = 1, int x = 0, int y = 0) {
  display.setTextSize(textSize);
  display.setCursor(x, y);
  display.println(msg);
}

void drawProgressBar(int x, int y, int width, int height, float progress) {
  display.drawRect(x, y, width, height, SSD1306_WHITE);
  int innerBarWidth = (int)(progress * (width - 4));
  if (innerBarWidth < 0) innerBarWidth = 0;
  display.fillRect(x + 2, y + 2, innerBarWidth, height - 4, SSD1306_WHITE);
}

// --- SPEAKER CONFIG ---
const int i2s_bclk = 5; // Bit Clock
const int i2s_lrc  = 4; // Word Select
const int i2s_din  = 6; // Data Input
#define SPEAKER_EN 7 // Pin connected to SD on the Amp

void setupI2S() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = 16000, // Match your recording rate
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT, // Mono
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 64
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = i2s_bclk,
    .ws_io_num = i2s_lrc,
    .data_out_num = i2s_din,
    .data_in_num = I2S_PIN_NO_CHANGE
  };

  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_config);
}

// Tambahkan fungsi pembantu ini di luar playRecording
int16_t softClip(int32_t sample) {
    // Jika sinyal melebihi batas 22000, kita "tekuk" sinyalnya alih-alih memotongnya secara tajam
    // Ini meniru karakteristik amplifier analog yang jernih
    if (sample > 22000) sample = 22000 + (sample - 22000) / 4;
    else if (sample < -22000) sample = -22000 + (sample - 22000) / 4;
    
    return (int16_t)constrain(sample, -32768, 32767);
}

void playRecording() {  
    size_t bytes_written;
    digitalWrite(SPEAKER_EN, HIGH); 
    delay(20); 

    int32_t mean = 0;
    for (size_t i = 0; i < samplesRecorded; i++) mean += fullBuffer[i];
    if (samplesRecorded > 0) mean /= (int32_t)samplesRecorded;

    // Pakai Gain yang kuat tapi terkontrol
    float loudGain = 15.0; 
    float alpha = 0.9; // Koefisien filter untuk memperhalus vokal
    int32_t lastFiltered = 0;

    for (size_t i = 0; i < samplesRecorded; i++) {
        // 1. Center sinyal
        int32_t rawSample = fullBuffer[i] - mean;

        // 2. Leaky High Pass Filter (Lebih halus dari sebelumnya)
        // Ini membuang noise rendah tanpa membuat suara jadi pecah tajam
        int32_t filtered = rawSample - lastFiltered;
        lastFiltered = (int32_t)(alpha * rawSample);

        // 3. Boost & Multi-stage Compression
        int32_t boosted = (int32_t)(filtered * loudGain);

        // Soft Knee Compression: Makin keras suaranya, makin kuat diredam
        if (abs(boosted) > 10000) {
            if (boosted > 10000) boosted = 10000 + (boosted - 10000) / 4;
            else boosted = -10000 + (boosted + 10000) / 4;
        }
        
        // Final Hard Limit sedikit di bawah batas maksimal 16-bit
        if (boosted > 30000) boosted = 30000;
        else if (boosted < -30000) boosted = -30000;

        fullBuffer[i] = (int16_t)boosted;
    }

    i2s_write(I2S_NUM_0, fullBuffer, samplesRecorded * sizeof(int16_t), &bytes_written, portMAX_DELAY);
    
    delay(200); 
    i2s_zero_dma_buffer(I2S_NUM_0);
    digitalWrite(SPEAKER_EN, LOW); 
}

// --- CORE FUNCTIONS ---
void sendData(String src, String out) {
  display.clearDisplay();
  updateScreen("SENDING...", 1, getXMid("SENDING..."), 30);
  display.display();

  String fullUrl = String(serverUrl) + "?SourceLanguage=" + src + "&OutputLanguage=" + out;
  size_t actualByteSize = samplesRecorded * sizeof(int16_t);

  HTTPClient http;
  http.begin(fullUrl);
  http.setTimeout(120000);
  http.addHeader("Content-Type", "application/octet-stream");

  int httpCode = http.POST((uint8_t*)fullBuffer, actualByteSize);

  if (httpCode == 200) {
    int len = http.getSize(); // Get the size of the returned WAV
    if (len > 0) {
      WiFiClient* stream = http.getStreamPtr();
      
      // We need to skip the 44-byte WAV header sent by FastAPI
      // so we only have raw PCM data in our buffer
      uint8_t headerDiscard[44];
      stream->readBytes(headerDiscard, 44);
      
      // Read the translated audio into your buffer
      int remainingData = len - 44;
      samplesRecorded = remainingData / 2; // Update count for playRecording
      
      stream->readBytes((uint8_t*)fullBuffer, remainingData);
      
      display.clearDisplay();
      updateScreen("RECEIVED!", 1, getXMid("RECEIVED!"), 30);
      display.display();
      
      delay(500);
      playRecording(); // Play the translated sound!
    }
  } else {
    display.clearDisplay();
    updateScreen("ERR: " + String(httpCode), 1, 0, 30);
    display.display();
    delay(2000);
  }

  delay(2000);
  samplesRecorded = 0;
}

bool connectWifi(const String& ssid, const String& password, unsigned long timeoutMs = 10000) {
  WiFi.begin(ssid.c_str(), password.c_str());

  unsigned long start = millis();

  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start >= timeoutMs) {
      Serial.println("\nWiFi connection TIMEOUT");
      return false;
    }

    delay(100);          // small yield (OK on ESP)
    Serial.print(".");
  }

  Serial.println("\nWiFi connected");
  return true;
}

void scanningWifi() {
  clearWifiList();
  int n = WiFi.scanNetworks();
  for (int i = 0; i < n; ++i) {
    if (i < availableWifiSize) {
      availableWifi[i] = WiFi.SSID(i);
    }
  }
}

void clearWifiList() {
  for (int i = 0; i < availableWifiSize; i++) {
    availableWifi[i] = "";
  }
}

int getNumOfAvailableWifi() {
  int result = 0;
  for (int i = 0; i < availableWifiSize; i++) {
    if (availableWifi[i] != "") result += 1;
  }
  return result;
}


// --- BUTTON CONFIG ---
int leftRightCounter = 0;
int upDownCounter = 0;
char* buttonHandler() {
  int upState = digitalRead(UP_BUTTON);
  int downState = digitalRead(DOWN_BUTTON);
  int rightState = digitalRead(RIGHT_BUTTON);
  int leftState = digitalRead(LEFT_BUTTON);
  int selectState = digitalRead(SELECT_BUTTON);
  delay(50);
  if (upState == 1 || downState == 1 || leftState == 1 || rightState == 1 || selectState == 1) {
    if (upState == 1) return "up";
    if (downState == 1) return "down";
    if (leftState == 1) return "left";
    if (rightState == 1) return "right";
    if (selectState == 1) return "select";
  }
  return "-";
}

// --- UI CONTROLLER ---
String selectedOPtion = "";
String menu[] = { "", "", "", "", "", "", "", "", "", "" };
int sizeOfMenu = sizeof(menu) / sizeof(menu[0]);
bool trigger = false;

void clearMenu() {
  for (int i = 0; i < sizeOfMenu; i++) {menu[i] = "";}
}

int countMenu() {
  int counter = 0;
  for (int i = 0; i < sizeOfMenu; i++) {
    if (menu[i] != "") {
      counter += 1;
    }
  }
  return counter;
}

void setMenu(String option[],int optionSize){
  for (int i = 0; i < optionSize; i++){
    if (i < sizeOfMenu){
      menu[i] = option[i];
    }else{
      return;
    }
  }
}

void optionSelect(String header) {
  if (buttonHandler() == "up" && upDownCounter > 0){
    upDownCounter -= 1;
  }
  if (buttonHandler() == "down" && upDownCounter < countMenu()-1){
    upDownCounter += 1;
  }
  
  display.clearDisplay();
  updateScreen(header, 2, getXMid(header,2), 0);
  int margin = 20;
  for (int i = 0; i < countMenu(); i++){
    String indicator = "  ";
    if (upDownCounter == i) indicator[0] = '>';
    updateScreen(indicator+menu[i],1,0,margin);
    margin += 10;
  }
  display.display();
  
  if (buttonHandler() == "select"){
    selectedOPtion = menu[upDownCounter];
  }
}

String getKeyFromInt(int idx) {
  if (idx == 0) return " ";
  if (idx > 0 && idx <= 10) return String(idx - 1);
  if (idx > 10 && idx <= 36) return String((char)(idx + 54));
  if (idx > 36 && idx <= 63) return String((char)(idx + 59));
  return "";
}

int getIdxFromKey(String data) {
  for (int i = 0; i < 64; i++) {
    if (getKeyFromInt(i) == data) return i;
  }
  return 0;
}

String typingBoard = "                     ";
void typingPage(String header) {
  String arrowHolder = "                     ";

  if (buttonHandler() == "right" && leftRightCounter < arrowHolder.length()-1){
    leftRightCounter += 1;
    upDownCounter = getIdxFromKey(String(typingBoard[leftRightCounter]));
  }
  if (buttonHandler() == "left"){
    if (leftRightCounter > 0){
      leftRightCounter -= 1;
      upDownCounter = getIdxFromKey(String(typingBoard[leftRightCounter]));
    }else changePage(2);
  }
  if (buttonHandler() == "up"){
    if (upDownCounter < 63){
      upDownCounter += 1;
    }
    else upDownCounter = 0;
  }
  if (buttonHandler() == "down"){
    if (upDownCounter >= 0){
      upDownCounter -= 1;
    }
    else upDownCounter = 63;
  }
  
  typingBoard[leftRightCounter] = getKeyFromInt(upDownCounter)[0];
  
  arrowHolder[leftRightCounter] = 'v';
  
  display.clearDisplay();
  updateScreen(header,1,getXMid(header),0);
  updateScreen(arrowHolder,1,0,getYMid()-10);
  updateScreen(typingBoard,1,0,getYMid());
  updateScreen("Press OK to Connect",1,getXMid("Press OK to Connect"),getYMid()+20);
  display.display();
}

// --- PAGE CONTROLLER ---
String page_option[] = { "selectWifi","typeWifiPassword","mainMenu", "translate" };
String current_page = page_option[2];
int page_option_size = sizeof(page_option) / sizeof(page_option[0]);

void translatePage() {
  display.clearDisplay();
  unsigned long currentTime = millis();
  float deltaTime = (currentTime - lastTime) / 1000.0;
  lastTime = currentTime;

  int btn1 = digitalRead(RECORD_BUTTON1);
  int btn2 = digitalRead(RECORD_BUTTON2);

  // --- HEADER ---
  display.fillRect(0, 0, 128, 12, SSD1306_WHITE);
  display.setTextColor(SSD1306_BLACK);
  updateScreen("TRANSLATOR", 1, getXMid("TRANSLATOR"), 2);
  display.setTextColor(SSD1306_WHITE);

  // --- RECORDING LOGIC ---
  if ((btn1 == HIGH || btn2 == HIGH) && recordTimer > 0) {
    pressedButton = (btn1 == HIGH) ? RECORD_BUTTON1 : RECORD_BUTTON2;
    send_API_trigger = true;
    samplesRecorded = 0;
    recordTimer = RECORD_TIME;
    nextSampleTime = micros();


    display.clearDisplay();
    display.fillRect(0, 0, 128, 12, SSD1306_WHITE);
    display.setTextColor(SSD1306_BLACK);
    updateScreen("TRANSLATOR", 1, getXMid("TRANSLATOR"), 2);
    display.setTextColor(SSD1306_WHITE);
    String srcS = sourceLanguage.substring(0, 3);
    srcS.toUpperCase();
    String outS = outputLanguage.substring(0, 3);
    outS.toUpperCase();
    updateScreen(srcS, 1, 5, 22);
    updateScreen(outS, 1, getXRight(outS) - 5, 22);
    if (pressedButton == RECORD_BUTTON1) updateScreen(">>>", 1, getXMid(">>>"), 22);
    if (pressedButton == RECORD_BUTTON2) updateScreen("<<<", 1, getXMid("<<<"), 22);

    display.drawFastHLine(0, 35, 128, SSD1306_WHITE);

    updateScreen("RECORDING...", 1, getXMid("RECORDING..."), 44);
    updateScreen("< Back",1,0,getYBottom(1));

    display.display();

    // DEDICATED SAMPLING LOOP (Blocks OLED to keep audio high quality)
    while (digitalRead(pressedButton) == HIGH && samplesRecorded < maxSamples) {
      if (micros() >= nextSampleTime) {
        int16_t raw = analogRead(ADC_INPUT_PIN);
        fullBuffer[samplesRecorded] = (raw - 2048) << 4;  // Center at 0
        samplesRecorded++;
        nextSampleTime += microsecondsPerSample;
      }

      // Update Timer & UI every 100ms within the while loop
      if (samplesRecorded % 1000 == 0) {
        yield();  // Feed watchdog
        recordTimer -= 0.1;
      }
    }
  }

  // --- POST-RECORDING MENU ---
  else if (send_API_trigger) {
    float actualDuration = (float)samplesRecorded / SAMPLE_RATE;

    if (actualDuration > 0.5) {
      display.clearDisplay();
      updateScreen("CONFIRM SEND?", 1, getXMid("CONFIRM SEND?"), 0);
      updateScreen("B1: TRANSLATE", 1, 0, 25);
      updateScreen("B2: CANCEL", 1, 0, 45);
      display.display();
      delay(1000);
      bool choiceSelected = false;
      bool proceed = false;

      while (!choiceSelected) {
        if (digitalRead(RECORD_BUTTON1) == HIGH) {
          proceed = true;
          choiceSelected = true;
        }
        if (digitalRead(RECORD_BUTTON2) == HIGH) {
          proceed = false;
          choiceSelected = true;
        }
        yield();
      }

      if (proceed) {
        String p1 = (pressedButton == RECORD_BUTTON1) ? sourceLanguage : outputLanguage;
        String p2 = (pressedButton == RECORD_BUTTON1) ? outputLanguage : sourceLanguage;
        sendData(p1, p2);
      }
      delay(200);
    } else {
      display.clearDisplay();
      updateScreen("TOO SHORT!", 1, getXMid("TOO SHORT!"), 30);
      display.display();
      delay(1500);
    }

    // Reset State
    send_API_trigger = false;
    recordTimer = RECORD_TIME;
    samplesRecorded = 0;
  }

  // --- IDLE UI ---
  else {
    updateScreen("HOLD TO SPEAK", 1, getXMid("HOLD TO SPEAK"), 44);

    String srcS = sourceLanguage.substring(0, 3);
    srcS.toUpperCase();
    String outS = outputLanguage.substring(0, 3);
    outS.toUpperCase();
    updateScreen(srcS, 1, 5, 22);
    updateScreen(outS, 1, getXRight(outS) - 5, 22);
    updateScreen("<=>", 1, getXMid("<=>"), 22);
    display.drawFastHLine(0, 35, 128, SSD1306_WHITE);
    updateScreen("< Back",1,0,getYBottom(1));
  }

  if (buttonHandler() == "left") changePage(2);

  display.display();
}


int scanningWifiInterval = 10;
float scanningWifiTimer = -1;
void selectWifiPage(){
  unsigned long currentTime = millis();
  float deltaTime = (currentTime - lastTime) / 1000.0;
  lastTime = currentTime;

  if (scanningWifiTimer <= 0){
    display.clearDisplay();
    updateScreen("Scanning Wifi",1,getXMid("Scanning Wifi"),getYMid());
    display.display();
    clearMenu();
    scanningWifi();
    if (upDownCounter > getNumOfAvailableWifi()) upDownCounter = getNumOfAvailableWifi();
    scanningWifiTimer = scanningWifiInterval;
  }
  else scanningWifiTimer -= deltaTime;


  setMenu(availableWifi,getNumOfAvailableWifi());
  optionSelect("WiFi");

  if (buttonHandler() == "select"){
    typingBoard = "                     ";
    changePage(1);
  }
  if (buttonHandler() == "left"){
    changePage(2);
  }
}

void typeWifiPasswordPage(){
  String ssid = selectedOPtion;
  ssid.trim();

  if(String(getData("ssid")) == ssid){
    display.clearDisplay();
    updateScreen("Connecting...",1,getXMid("Connecting..."),getYMid());
    display.display();
    String msg = connectWifi(ssid,String(getData("password")),10000) ? "Success":"Failed";
    if (msg == "Success"){
      display.clearDisplay();
      updateScreen("Connected",1,getXMid("Connected"),getYMid());
      display.display();
      delay(3000);
      changePage(2);
      return;
    }else {
      display.clearDisplay();
      updateScreen("Fail to Connect",1,getXMid("Fail to Connect"),getYMid());
      display.display();

      addData("ssid","");
      addData("password","");

      delay(3000);
    }
  }

  typingPage("Wifi Password");
  if (buttonHandler() == "select"){
    display.clearDisplay();
    updateScreen("Connecting...",1,getXMid("Connecting..."),getYMid());
    display.display();

    display.clearDisplay();
    String password = typingBoard;
    password.trim();
    
    String msg = connectWifi(ssid,password,10000) ? "Success":"Failed";
    updateScreen(msg,1,getXMid(msg,1),getYMid());
    if (msg == "Success") {addData("ssid",ssid); addData("password",password);}
    else {addData("ssid",""); addData("password","");}
    delay(3000);
    changePage(2);

    display.display();
  }
}

void mainMenu(){
  String menu[] = {String(page_option[0]),String(page_option[3])};
  setMenu(menu,2);
  optionSelect("Main Menu");

  if (buttonHandler() == "select"){
    int pageIdx = 0;
    for (int i = 0; i < page_option_size; i++){
      if (page_option[i] == menu[upDownCounter]){
        changePage(i);
      }
    }
  }
}

void changePage(int pageIdx) {
  current_page = page_option[pageIdx];
  upDownCounter = 0;
  leftRightCounter = 0;
  clearMenu();
}

void setup() {
  Serial.begin(115200);
  pinMode(RECORD_BUTTON1, INPUT_PULLDOWN);
  pinMode(RECORD_BUTTON2, INPUT_PULLDOWN);
  analogReadResolution(12);

  pinMode(UP_BUTTON, INPUT_PULLDOWN);
  pinMode(DOWN_BUTTON, INPUT_PULLDOWN);
  pinMode(SELECT_BUTTON, INPUT_PULLDOWN);
  pinMode(LEFT_BUTTON, INPUT_PULLDOWN);
  pinMode(RIGHT_BUTTON, INPUT_PULLDOWN);

  pinMode(SPEAKER_EN, OUTPUT);
  digitalWrite(SPEAKER_EN, LOW);
  setupI2S(); 

  // Allocate Buffer with Safety Check
  fullBuffer = (int16_t*)ps_malloc(maxSamples * sizeof(int16_t));
  if (!fullBuffer) fullBuffer = (int16_t*)malloc(maxSamples * sizeof(int16_t));
  
  if (!fullBuffer) {
    Serial.println("Memory Allocation Failed!");
    // You might want to show this on the display too
  }

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) while (1);
  display.setTextColor(SSD1306_WHITE);
  display.clearDisplay();

  lastTime = millis();
  
  // REMOVE scanningWifi(); from here
  Serial.println("Setup Complete");
}

void loop() {
  if (current_page == page_option[0]){
    selectWifiPage();
  }
  if (current_page == page_option[1]){
    typeWifiPasswordPage();
  }
  if (current_page == page_option[2]){
    mainMenu();
  }
  if (current_page == page_option[3]){
    if (WiFi.status() != WL_CONNECTED){
      display.clearDisplay();
      updateScreen("No Connection!",1,getXMid("No Connection!"),getYMid());
      display.display();
      delay(3000);
      changePage(0);
    }else translatePage();
  }
}