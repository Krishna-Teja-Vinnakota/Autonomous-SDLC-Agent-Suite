import { useState } from 'react';
import './ProfileForm.css';

// ✅ FIXED VERSION - Full Validation as per KAN-274
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

  // ✅ FIX: Validate each field
  const validateField = (name: string, value: string): string | null => {
    switch (name) {
      case 'name':
        if (!value.trim()) return 'Name is required';
        if (value.length < 3) return 'Name must be at least 3 characters';
        if (value.length > 50) return 'Name must not exceed 50 characters';
        if (!/^[a-zA-Z\s]+$/.test(value)) return 'Name can only contain letters and spaces';
        return null;

      case 'email':
        if (!value.trim()) return 'Email is required';
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return 'Please enter a valid email address';
        return null;

      case 'phone':
        if (!value.trim()) return 'Phone number is required';
        if (!/^\d{10}$/.test(value)) return 'Phone number must be exactly 10 digits';
        return null;

      case 'age':
        const ageNum = parseInt(value);
        if (!value) return 'Age is required';
        if (isNaN(ageNum)) return 'Age must be a number';
        if (ageNum < 18) return 'Age must be at least 18';
        if (ageNum > 100) return 'Age must not exceed 100';
        return null;

      case 'bio':
        if (value.length > 200) return 'Bio must not exceed 200 characters';
        return null;

      default:
        return null;
    }
  };

  // ✅ FIX: Validate all fields
  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    const nameError = validateField('name', formData.name);
    if (nameError) newErrors.name = nameError;

    const emailError = validateField('email', formData.email);
    if (emailError) newErrors.email = emailError;

    const phoneError = validateField('phone', formData.phone);
    if (phoneError) newErrors.phone = phoneError;

    const ageError = validateField('age', formData.age);
    if (ageError) newErrors.age = ageError;

    const bioError = validateField('bio', formData.bio);
    if (bioError) newErrors.bio = bioError;

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // ✅ FIX: Check if form is valid
  const isFormValid = (): boolean => {
    return (
      formData.name.trim().length >= 3 &&
      formData.name.length <= 50 &&
      /^[a-zA-Z\s]+$/.test(formData.name) &&
      /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email) &&
      /^\d{10}$/.test(formData.phone) &&
      parseInt(formData.age) >= 18 &&
      parseInt(formData.age) <= 100 &&
      formData.bio.length <= 200
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage('');

    // ✅ FIX: Validate before submit
    if (!validateForm()) {
      return;
    }

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
        setErrors({});
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
    
    // ✅ FIX: Validate on change to show errors in real-time
    const error = validateField(name, value);
    setErrors(prev => {
      const newErrors = { ...prev };
      if (error) {
        newErrors[name] = error;
      } else {
        delete newErrors[name];
      }
      return newErrors;
    });
  };

  // ✅ FIX: Also validate on blur (when user leaves field)
  const handleBlur = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    const error = validateField(name, value);
    if (error) {
      setErrors(prev => ({ ...prev, [name]: error }));
    }
  };

  return (
    <div className="profile-form-container">
      <div className="profile-form-card">
        <h2 className="profile-form-title">Update Your Profile</h2>
        <p className="profile-form-subtitle">Keep your information up to date</p>

        <form onSubmit={handleSubmit} className="profile-form">
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
              onBlur={handleBlur}
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
              type="text"
              placeholder="your.email@example.com"
              value={formData.email}
              onChange={handleChange}
              onBlur={handleBlur}
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
              type="text"
              placeholder="10 digits (e.g., 1234567890)"
              value={formData.phone}
              onChange={handleChange}
              onBlur={handleBlur}
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
              onBlur={handleBlur}
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
              onBlur={handleBlur}
              rows={4}
              className={errors.bio ? 'input-error' : ''}
            />
            <small className="char-count">{formData.bio.length}/200 characters</small>
            {errors.bio && <span className="error-message" data-testid="bio-error">{errors.bio}</span>}
          </div>

          {/* ✅ FIX: Button disabled when form invalid */}
          <button 
            type="submit" 
            data-testid="save-button"
            className="submit-button"
            disabled={loading || !isFormValid()}
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
