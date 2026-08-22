import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ChartRenderer from './ChartRenderer';
import React from 'react';

describe('ChartRenderer', () => {
  const dummyData = [
    { category: 'A', value: 10 },
    { category: 'B', value: 20 },
  ];

  it('renders a table by default when no spec is provided', () => {
    render(<ChartRenderer data={dummyData} />);
    // Doit contenir le texte "Tableau" et les en-têtes
    expect(screen.getByText('category')).toBeInTheDocument();
    expect(screen.getByText('value')).toBeInTheDocument();
  });

  it('renders a metric chart correctly', () => {
    const spec = { chart_type: 'metric', y_field: 'value' };
    render(<ChartRenderer data={dummyData} chartSpec={spec} />);
    expect(screen.getByText('10')).toBeInTheDocument(); // Première valeur
  });

  it('displays a warning if the backend sends one', () => {
    const spec = { chart_type: 'table', warnings: ['Données incompatibles'] };
    render(<ChartRenderer data={dummyData} chartSpec={spec} />);
    expect(screen.getByText('Données incompatibles')).toBeInTheDocument();
  });

  it('does not crash on empty data', () => {
    const { container } = render(<ChartRenderer data={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('handles null or missing values gracefully in table', () => {
    const nullData = [{ category: 'A', value: null }];
    render(<ChartRenderer data={nullData} />);
    // La table doit s'afficher sans erreur
    expect(screen.getByText('category')).toBeInTheDocument();
  });
});
