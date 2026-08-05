# Known faces (enrollment)

Put a few clear photos of each person in a **folder named after them**:

```
known_faces/
  Alice/
    img1.jpg
    img2.jpg
  Bob/
    face.png
```

Then rebuild:

```powershell
python -m facial_recognition.enroll --rebuild
```

Or capture from webcam:

```powershell
python -m facial_recognition.enroll --capture Alice --count 5 --rebuild
```
