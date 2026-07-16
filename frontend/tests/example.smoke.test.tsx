import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PlaceholderPage from '@/components/PlaceholderPage';
import ScoringReport from '@/pages/ScoringReport';

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
    // 通过 @/ 别名深度 import 页面组件（其内部同样以 @/ 引用 PlaceholderPage），
    // 验证 vite alias 与 tsconfig paths 在测试环境下一致。
    render(
      <MemoryRouter>
        <ScoringReport />
      </MemoryRouter>,
    );
    expect(screen.getAllByText('评分报告').length).toBeGreaterThan(0);
  });
});
