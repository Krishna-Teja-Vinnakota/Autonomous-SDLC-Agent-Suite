import { useState, useEffect } from 'react';
import './ProfileForm.css';

export default function ProfileForm() {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    age: '',
    bio: ''
  });
  const [message, setMessage] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [isFormValid, setIsFormValid] = useState(false);

  useEffect(() => {
    const validate = () => {
      const newErrors: Record<string, string> = {};

      // Name validation
      if (formData.name.length < 3 || formData.name.length > 50) {
        newErrors.name = 'Name must be between 3 and 50 characters.';
      } else if (!/^[a-zA-Z\s]+$/.test(formData.name)) {
        newErrors.name = 'Name can only contain letters and spaces.';
      }

      // Email validation
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
        newErrors.email = 'Please enter a valid email address.';
      }

      // Phone validation
      if (!/^\d{10}$/.test(formData.phone)) {
        newErrors.phone = 'Phone number must be exactly 10 digits.';
      }

      // Age validation
      const ageNum = Number(formData.age);
      if (isNaN(ageNum) || ageNum < 18 || ageNum > 100) {
        newErrors.age = 'Age must be a number between 18 and 100.';
      }

      // Bio validation
      if (formData.bio.length > 200) {
        newErrors.bio = 'Bio cannot exceed 200 characters.';
      }

      setErrors(newErrors);
      setIsFormValid(Object.keys(newErrors).length === 0);
    };

    validate();
  }, [formData]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!isFormValid) {
      return;
    }

    setMessage('');
    setLoading(true);

    try {
      const response = await fetch('http://localhost:3001/api/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      const data = await response.json();

      if (response.ok) {
        setMessage('Profile updated successfully');
      } else {
        setErrors(data.errors || {});
      }
    } catch (error) {
      setMessage('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setMessage('');
  };

  return (
    <div className="profile-form-container">
      <div className="profile-form-card">
        <h2 className="profile-form-title">Update Your Profile</h2>
        <p className="profile-form-subtitle">Keep your information up to date</p>

        <form onSubmit={handleSubmit} className="profile-form" noValidate>
          <div className="form-group">
            <label htmlFor="name">Full Name *</label>
            <input
              id="name"
              name="name"
              data-testid="name-input"
              type="text"
              placeholder="Enter your full name (3-50 characters)"
              value={formData.name}
              onChange={handleChange}
              className={errors.name ? 'input-error' : ''}
            />
            {errors.name && <span className="error-message" data-testid="name-error">{errors.name}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="email">Email Address *</label>
            <input
              id="email"
              name="email"
              data-testid="email-input"
              type="email"
              placeholder="your.email@example.com"
              value={formData.email}
              onChange={handleChange}
              className={errors.email ? 'input-error' : ''}
            />
            {errors.email && <span className="error-message" data-testid="email-error">{errors.email}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="phone">Phone Number *</label>
            <input
              id="phone"
              name="phone"
              data-testid="phone-input"
              type="tel"
              placeholder="10 digits (e.g., 1234567890)"
              value={formData.phone}
              onChange={handleChange}
              className={errors.phone ? 'input-error' : ''}
            />
            {errors.phone && <span className="error-message" data-testid="phone-error">{errors.phone}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="age">Age *</label>
            <input
              id="age"
              name="age"
              data-testid="age-input"
              type="number"
              placeholder="Must be between 18-100"
              value={formData.age}
              onChange={handleChange}
              className={errors.age ? 'input-error' : ''}
            />
            {errors.age && <span className="error-message" data-testid="age-error">{errors.age}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="bio">Bio (Optional)</label>
            <textarea
              id="bio"
              name="bio"
              data-testid="bio-input"
              placeholder="Tell us about yourself (max 200 characters)"
              value={formData.bio}
              onChange={handleChange}
              rows={4}
              className={errors.bio ? 'input-error' : ''}
            />
            <small className="char-count">{formData.bio.length}/200 characters</small>
            {errors.bio && <span className="error-message" data-testid="bio-error">{errors.bio}</span>}
          </div>

          <button 
            type="submit" 
            data-testid="save-button"
            className="submit-button"
            disabled={!isFormValid || loading}
          >
            {loading ? 'Saving...' : 'Save Profile'}
          </button>
        </form>

        {message && (
          <div className="success-message" data-testid="success-message">
            ✓ {message}
          </div>
        )}
      </div>
    </div>
  );
}