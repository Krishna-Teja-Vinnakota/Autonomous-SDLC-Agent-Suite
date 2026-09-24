import express from 'express';
import cors from 'cors';

const app = express();
const PORT = 3001;

app.use(cors());
app.use(express.json());

let userProfile = {
  name: 'John Doe',
  email: 'john@example.com',
  phone: '1234567890',
  age: 25,
  bio: 'Software developer'
};

// ❌ BUGGY VERSION - NO VALIDATION!
app.put('/api/profile', (req, res) => {
  const { name, email, phone, age, bio } = req.body;

  console.log('📥 Received:', { name, email, phone, age, bio });

  // ❌ BUG: Accepts ANYTHING - no validation!
  userProfile = {
    name: name || userProfile.name,
    email: email || userProfile.email,
    phone: phone || userProfile.phone,
    age: age || userProfile.age,
    bio: bio || userProfile.bio
  };

  console.log('✅ Updated (NO validation!):', userProfile);

  res.json({
    success: true,
    message: 'Profile updated successfully',
    data: userProfile
  });
});

app.get('/api/profile', (req, res) => {
  res.json({ success: true, data: userProfile });
});

app.get('/health', (req, res) => {
  res.json({ status: 'ok', message: 'Buggy server - NO validation!' });
});

app.get('/', (req, res) => {
  res.json({ message: 'Profile API Server', version: 'buggy' });
});

app.listen(PORT, () => {
  console.log(`🚀 BUGGY Server on http://localhost:${PORT}`);
  console.log(`⚠️  WARNING: NO VALIDATION - Accepts any data!`);
});
