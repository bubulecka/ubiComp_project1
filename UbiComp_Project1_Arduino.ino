/*
  Arduino Nano 33 BLE Sense - LPS22HB - Read Pressure
*/

#include <Arduino_LPS22HB.h>

void setup() {
  Serial.begin(9600);
  while (!Serial)
    ;

  if (!BARO.begin()) {
    Serial.println("Failed to initialize pressure sensor!");
    while (1)
      ;
  }

  // set LED's pin to output mode
  pinMode(LEDR, OUTPUT);
  pinMode(LEDG, OUTPUT);
  pinMode(LEDB, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);

  digitalWrite(LED_BUILTIN, HIGH);  // will turn the LED off
  digitalWrite(LEDR, HIGH);         // will turn the LED off
  digitalWrite(LEDG, HIGH);         // will turn the LED off
  digitalWrite(LEDB, HIGH);         // will turn the LED off
}

void loop() {
  // check for input
  recvOneChar();

  // read the sensor value
  float pressure = BARO.readPressure();
  Serial.print("pressure:");
  Serial.println(pressure);

  float altitude = 44330 * (1 - pow(pressure / 101.325, 1 / 5.255));
  Serial.print("altitude:");
  Serial.println(altitude);

  float temperature = BARO.readTemperature();
  Serial.print("temperature:");
  Serial.println(temperature);

  // print an empty line
  Serial.println();

  // wait 1 second to print again
  delay(1000);
}

void recvOneChar() {
  if (Serial.available() > 0) {
    char receivedChar = Serial.read();

    switch (receivedChar) {  // any value other than 0
      case 'r':
        Serial.println("Red LED on");
        digitalWrite(LEDR, LOW);   // will turn the LED on
        digitalWrite(LEDG, HIGH);  // will turn the LED off
        digitalWrite(LEDB, HIGH);  // will turn the LED off
        break;
      case 'g':
        Serial.println("Green LED on");
        digitalWrite(LEDR, HIGH);  // will turn the LED off
        digitalWrite(LEDG, LOW);   // will turn the LED on
        digitalWrite(LEDB, HIGH);  // will turn the LED off
        break;
      case 'b':
        Serial.println("Blue LED on");
        digitalWrite(LEDR, HIGH);  // will turn the LED off
        digitalWrite(LEDG, HIGH);  // will turn the LED off
        digitalWrite(LEDB, LOW);   // will turn the LED on
        break;
      default:
        Serial.println(F("LEDs off"));
        digitalWrite(LEDR, HIGH);  // will turn the LED off
        digitalWrite(LEDG, HIGH);  // will turn the LED off
        digitalWrite(LEDB, HIGH);  // will turn the LED off
        break;
    }
  }
}
