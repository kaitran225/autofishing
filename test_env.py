import sys
import os
import datetime

print("=== TEST ENVIRONMENT ===")
print(f"Python version: {sys.version}")
print(f"Platform: {sys.platform}")
print(f"Current directory: {os.getcwd()}")
print(f"Current time: {datetime.datetime.now()}")

# Try to write to a file
try:
    with open('test_output.txt', 'w') as f:
        f.write(f"Test file written at {datetime.datetime.now()}\n")
        f.write(f"Python version: {sys.version}\n")
        f.write(f"Platform: {sys.platform}\n")
    print("Successfully wrote to test_output.txt")
except Exception as e:
    print(f"Error writing to file: {e}")

print("=== TEST COMPLETE ===") 