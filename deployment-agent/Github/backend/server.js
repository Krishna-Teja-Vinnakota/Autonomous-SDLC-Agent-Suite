import express from 'express';
import cors from 'cors';

const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());

let userProfile = {
  name: 'John Doe',
  email: 'john@example.com',
  phone: '1234567890',
  age: 25,
  bio: 'Software developer'
};

// ✅ FIXED VERSION - Complete Validation as per KAN-275
app.put('/api/profile', (req, res) => {
  const { name, email, phone, age, bio } = req.body;

  console.log('📥 Received:', { name, email, phone, age, bio });

  const errors = {};

  // ✅ FIX: Name validation (3-50 chars, letters/spaces only)
  if (!name || !name.trim()) {
    errors.name = 'Name is required';
  } else if (name.length < 3) {
    errors.name = 'Name must be at least 3 characters';
  } else if (name.length > 50) {
    errors.name = 'Name must not exceed 50 characters';
  } else if (!/^[a-zA-Z\s]+$/.test(name)) {
    errors.name = 'Name can only contain letters and spaces';
  }

  // ✅ FIX: Email validation
  if (!email || !email.trim()) {
    errors.email = 'Email is required';
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    errors.email = 'Please enter a valid email address';
  }

  // ✅ FIX: Phone validation (exactly 10 digits)
  if (!phone || !phone.trim()) {
    errors.phone = 'Phone number is required';
  } else if (!/^\d{10}$/.test(phone)) {
    errors.phone = 'Phone number must be exactly 10 digits';
  }

  // ✅ FIX: Age validation (18-100)
  const ageNum = parseInt(age);
  if (!age) {
    errors.age = 'Age is required';
  } else if (isNaN(ageNum)) {
    errors.age = 'Age must be a number';
  } else if (ageNum < 18) {
    errors.age = 'Age must be at least 18';
  } else if (ageNum > 100) {
    errors.age = 'Age must not exceed 100';
  }

  // ✅ FIX: Bio validation (max 200 chars, optional)
  if (bio && bio.length > 200) {
    errors.bio = 'Bio must not exceed 200 characters';
  }

  // ✅ FIX: Return 400 if validation errors
  if (Object.keys(errors).length > 0) {
    console.log('❌ Validation failed:', errors);
    return res.status(400).json({
      success: false,
      message: 'Validation failed',
      errors
    });
  }

  // ✅ FIX: Update only if valid
  userProfile = {
    name,
    email,
    phone,
    age: ageNum,
    bio: bio || ''
  };

  console.log('✅ Profile updated (with validation):', userProfile);

  // ✅ FIX: Return 200 for success
  res.status(200).json({
    success: true,
    message: 'Profile updated successfully',
    data: userProfile
  });
});

app.get('/api/profile', (req, res) => {
  res.json({ success: true, data: userProfile });
});

app.get('/health', (req, res) => {
  res.json({ status: 'ok', message: 'Fixed server - Full validation!' });
});

app.get('/', (req, res) => {
  res.json({ message: 'Profile API Server', version: 'fixed' });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 FIXED Server on http://localhost:${PORT}`);
  console.log(`✅ All validation implemented!`);
});
