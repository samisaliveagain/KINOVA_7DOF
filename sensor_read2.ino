/*
 *  This sketch sends imu data over UDP on a ESP32
 *
 */
#include <WiFi.h>
#include <NetworkUdp.h>
#include "I2Cdev.h"
#include "MPU6050_6Axis_MotionApps20.h"
#include "AiEsp32RotaryEncoder.h"
#include <OneButton.h>

// WiFi network name and password:
const char *networkName = "Your Wifi";
const char *networkPswd = "Your Pwd";

//IP address to send UDP data to:
// either use the ip address of the server or
// a network broadcast address
const char *udpAddress = "Your Host IP";
const int udpPort = 5000;



//encoder input pins
#define dt 26
#define clk 25
#define sw 27
#define inf 14

//encoder counter definetions

int counter = 0; 
int aState;
int aLastState;
int counterprev = 0; 
int swState;
int swLong;
int mode = 0;
int infState;
//paramaters for button
unsigned long shortPressAfterMiliseconds = 50;   //how long short press shoud be. Do not set too low to avoid bouncing (false press events).
unsigned long longPressAfterMiliseconds = 1000;  //how long čong press shoud be.

AiEsp32RotaryEncoder rotaryEncoder = AiEsp32RotaryEncoder(dt, clk, sw, -1, 4);
OneButton btn;

//Are we currently connected?
boolean connected = false;

//class definitoins
NetworkUDP udp;
MPU6050 mpu;

/*Conversion variables*/
#define EARTH_GRAVITY_MS2 9.80665  //m/s2
#define DEG_TO_RAD        0.017453292519943295769236907684886
#define RAD_TO_DEG        57.295779513082320876798154814105

/*---MPU6050 Control/Status Variables---*/
bool DMPReady = false;  // Set true if DMP init was successful
uint8_t MPUIntStatus;   // Holds actual interrupt status byte from MPU
uint8_t devStatus;      // Return status after each device operation (0 = success, !0 = error)
uint16_t packetSize;    // Expected DMP packet size (default is 42 bytes)
uint8_t FIFOBuffer[64]; // FIFO storage buffer

/*---MPU6050 Control/Status Variables---*/
Quaternion q;           // [w, x, y, z]         Quaternion container
VectorInt16 aa;         // [x, y, z]            Accel sensor measurements
VectorInt16 gg;         // [x, y, z]            Gyro sensor measurements
VectorInt16 aaWorld;    // [x, y, z]            World-frame accel sensor measurements
VectorInt16 ggWorld;    // [x, y, z]            World-frame gyro sensor measurements
VectorFloat gravity;    // [x, y, z]            Gravity vector
float euler[3];         // [psi, theta, phi]    Euler angle container
float ypr[3];           // [yaw, pitch, roll]   Yaw/Pitch/Roll container and gravity vector




void IRAM_ATTR readEncoderISR()
{
    rotaryEncoder.readEncoder_ISR();
}

// Handler function for a single click:
static void handleClick() {
  if (swState == 0){
    swState = 1;
  }else{
    swState = 0;
  }
}

// Handler function for a long press release:
static void attachDuringLongPress() {
  swLong = (btn.getPressedMs() > 1000);
}

// Handler function for a long press release:
static void attachLongPressStop() {
  swLong = 0;
}

void setup() {

  //encoder pin setup
 // pinMode (dt, INPUT);
  //pinMode (clk, INPUT);
  // pinMode (sw, INPUT);
  btn.setup(
  sw,   // Input pin for the button
  INPUT_PULLUP, // INPUT and enable the internal pull-up resistor
  true          // Button is active LOW
  );

  // Single Click event attachment
  btn.attachClick(handleClick);
  btn.attachDuringLongPress(attachDuringLongPress);
  btn.attachLongPressStop(attachLongPressStop);
  btn.setDebounceMs(20);

  rotaryEncoder.begin();
  rotaryEncoder.setup(readEncoderISR);
  rotaryEncoder.setBoundaries(0, 1000, false); //minValue, maxValue, circleValues true|false (when max go to min and vice versa)
  rotaryEncoder.disableAcceleration();

  //inftared prox sensor pin setup
  pinMode (inf, INPUT_PULLUP);


  //use fast i2c if available

  #if I2CDEV_IMPLEMENTATION == I2CDEV_ARDUINO_WIRE
    Wire.begin();
    Wire.setClock(400000); // 400kHz I2C clock. Comment on this line if having compilation difficulties
  #elif I2CDEV_IMPLEMENTATION == I2CDEV_BUILTIN_FASTWIRE
    Fastwire::setup(400, true);
  #endif

  connectToWiFi(networkName, networkPswd);


  // Initialize hardware serial:
  Serial.begin(115200);
  Wire.begin(21, 22); // SDA, SCL
  Serial.println(F("Initializing I2C devices..."));
  mpu.initialize();
  Serial.println(F("Testing MPU6050 connection..."));
  if(mpu.testConnection() == false){
    Serial.println("MPU6050 connection failed");
    while(true);
  }
  else {
    Serial.println("MPU6050 connection successful");
  }
  
  /* Initializate and configure the DMP*/
  Serial.println(F("Initializing DMP..."));
  devStatus = mpu.dmpInitialize();

  /* Supply your gyro offsets here, scaled for min sensitivity */
  mpu.setXGyroOffset(0);
  mpu.setYGyroOffset(0);
  mpu.setZGyroOffset(0);
  mpu.setXAccelOffset(0);
  mpu.setYAccelOffset(0);
  mpu.setZAccelOffset(0);

  /* Making sure it worked (returns 0 if so) */ 
  if (devStatus == 0) {
    mpu.CalibrateAccel(6);  // Calibration Time: generate offsets and calibrate our MPU6050
    mpu.CalibrateGyro(6);
    Serial.println("These are the Active offsets: ");
    mpu.PrintActiveOffsets();
    Serial.println(F("Enabling DMP..."));   //Turning ON DMP
    mpu.setDMPEnabled(true);

    MPUIntStatus = mpu.getIntStatus();

    /* Set the DMP Ready flag so the main loop() function knows it is okay to use it */
    Serial.println(F("DMP ready! Waiting for first interrupt..."));
    DMPReady = true;
    packetSize = mpu.dmpGetFIFOPacketSize(); //Get expected DMP packet size for later comparison
  }
  //Connect to the WiFi network
  
}

int last;

void loop() {

  if (!DMPReady) return;


    //infrared detect
  infState = digitalRead(inf);

  //encoder logic
  //swState = digitalRead(sw); // read switch state
  btn.tick();


    if (rotaryEncoder.encoderChanged())
    {   
      counter = rotaryEncoder.readEncoder();
      if (counter%2 == 0 && counterprev < counter)
      { 
        mode++;
        counterprev = counter;
        if (mode > 2)
        { mode=2;}
      }
      if (counter%2 == 0 && counterprev > counter)
      { 
        mode--;
        counterprev = counter;
        if (mode < 0)
        { mode=0;}
      }
    }

  Serial.println(counter);
  Serial.println(mode);

  /* Read a packet from FIFO */
  if (mpu.dmpGetCurrentFIFOPacket(FIFOBuffer)) { // Get the Latest packet 
    /*Display quaternion values in easy matrix form: w x y z */
    mpu.dmpGetQuaternion(&q, FIFOBuffer);
    Serial.print("quat\t");
    Serial.print(q.w);
    Serial.print("\t");
    Serial.print(q.x);
    Serial.print("\t");
    Serial.print(q.y);
    Serial.print("\t");
    Serial.println(q.z);

    mpu.dmpGetGravity(&gravity, &q);

    /* Display initial world-frame acceleration, adjusted to remove gravity
    and rotated based on known orientation from Quaternion */
    mpu.dmpGetAccel(&aa, FIFOBuffer);
    mpu.dmpConvertToWorldFrame(&aaWorld, &aa, &q);
    Serial.print("aworld\t");
    Serial.print(aaWorld.x * mpu.get_acce_resolution() * EARTH_GRAVITY_MS2);
    Serial.print("\t");
    Serial.print(aaWorld.y * mpu.get_acce_resolution() * EARTH_GRAVITY_MS2);
    Serial.print("\t");
    Serial.println(aaWorld.z * mpu.get_acce_resolution() * EARTH_GRAVITY_MS2);

    /* Display initial world-frame acceleration, adjusted to remove gravity
    and rotated based on known orientation from Quaternion */
    mpu.dmpGetGyro(&gg, FIFOBuffer);
    mpu.dmpConvertToWorldFrame(&ggWorld, &gg, &q);
    Serial.print("ggWorld\t");
    Serial.print(ggWorld.x * mpu.get_gyro_resolution() * DEG_TO_RAD);
    Serial.print("\t");
    Serial.print(ggWorld.y * mpu.get_gyro_resolution() * DEG_TO_RAD);
    Serial.print("\t");
    Serial.println(ggWorld.z * mpu.get_gyro_resolution() * DEG_TO_RAD);

    /* Display Euler angles in degrees */
    mpu.dmpGetYawPitchRoll(ypr, &q, &gravity);
    Serial.print("ypr\t");
    Serial.print(ypr[0] * RAD_TO_DEG);
    Serial.print("\t");
    Serial.print(ypr[1] * RAD_TO_DEG);
    Serial.print("\t");
    Serial.println(ypr[2] * RAD_TO_DEG);
    
    Serial.println();
  }

  //only send data when connected
  
    //Send a packet
    udp.beginPacket(udpAddress, udpPort);
    
    udp.printf("%.2f,%.2f,%.2f,%i,%i,%i,%i", ypr[0], ypr[1], ypr[2], mode, swState, infState, swLong);
    udp.endPacket();
  
  //Wait for 1 second
  delay(50);
}

void connectToWiFi(const char *ssid, const char *pwd) {
  Serial.println("Connecting to WiFi network: " + String(ssid));

  // delete old config
  WiFi.disconnect(true);
  //register event handler
  WiFi.onEvent(WiFiEvent);  // Will call WiFiEvent() from another thread.

  //Initiate connection
  WiFi.begin(ssid, pwd);

  Serial.println("Waiting for WIFI connection...");
}

// WARNING: WiFiEvent is called from a separate FreeRTOS task (thread)!
void WiFiEvent(WiFiEvent_t event) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_STA_GOT_IP:
      //When connected set
      Serial.print("WiFi connected! IP address: ");
      Serial.println(WiFi.localIP());
      //initializes the UDP state
      //This initializes the transfer buffer
      udp.begin(WiFi.localIP(), udpPort);
      connected = true;
      break;
    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
      Serial.println("WiFi lost connection");
      connected = false;
      break;
    default: break;
  }
}