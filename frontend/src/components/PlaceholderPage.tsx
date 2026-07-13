import React from 'react';
import { Button } from 'antd';
import { useNavigate } from 'react-router-dom';

interface PlaceholderPageProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  showBackButton?: boolean;
}

const PlaceholderPage: React.FC<PlaceholderPageProps> = ({ icon, title, description, showBackButton = true }) => {
  const navigate = useNavigate();
  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: 4 }}>{title}</h1>
      </div>
      <div className="placeholder-page" style={{ marginTop: 40 }}>
        <div className="placeholder-icon">{icon}</div>
        <div className="placeholder-title">{title}</div>
        <div className="placeholder-desc">{description}</div>
        {showBackButton && (
          <Button type="primary" onClick={() => navigate('/')} style={{ marginTop: 24, borderRadius: 'var(--radius-md)' }}>
            返回看板
          </Button>
        )}
      </div>
    </div>
  );
};

export default PlaceholderPage;
