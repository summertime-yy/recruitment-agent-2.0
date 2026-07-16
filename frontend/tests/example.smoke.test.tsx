import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PlaceholderPage from '@/components/PlaceholderPage';
import { matchApi } from '@/services/match';

describe('前端测试基建 smoke', () => {
  test('test_placeholder_component_renders', () => {
    render(
      <MemoryRouter>
        <PlaceholderPage
          icon={<span>icon</span>}
          title="评分报告"
          description="smoke"
          showBackButton={false}
        />
      </MemoryRouter>,
    );
    expect(screen.getAllByText('评分报告').length).toBeGreaterThan(0);
  });

  test('test_alias_import_works', () => {
    // 验证 @/ 别名可解析 TS 模块（service）
    expect(typeof matchApi.matchOne).toBe('function');
    expect(typeof matchApi.rankByJd).toBe('function');
  });
});
