import requests
import time

def test_image_caching(image_url):
    print("Test 1: First request (should return 200)")
    # First request
    response1 = requests.get(image_url)
    print(f"Status Code: {response1.status_code}")
    print(f"Headers: {dict(response1.headers)}\n")
    
    if 'ETag' not in response1.headers:
        print("Error: No ETag in response!")
        return
        
    etag = response1.headers['ETag']
    
    print("Test 2: Second request with ETag (should return 304)")
    # Second request with ETag
    headers = {'If-None-Match': etag}
    response2 = requests.get(image_url, headers=headers)
    print(f"Status Code: {response2.status_code}")
    print(f"Headers: {dict(response2.headers)}\n")

if __name__ == "__main__":
    # 替换为您的实际图片URL
    image_url = "http://127.0.0.1:5000/uploads/IMG_9378.jpg"
    test_image_caching(image_url)
