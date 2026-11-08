import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Field, TextInput } from '@/components/Field';

describe('Field', () => {
  it('ties the label to its input and announces that it is required', () => {
    render(
      <Field id="customers" label="Target customers" required>
        {(control) => <TextInput {...control} />}
      </Field>,
    );

    const input = screen.getByLabelText(/target customers/i);
    expect(input).toHaveAttribute('id', 'customers');
    expect(input).toHaveAttribute('aria-required', 'true');
    expect(screen.getByText('(required)')).toBeInTheDocument();
  });

  it('describes the input with its helper text', () => {
    render(
      <Field id="idea" label="Your idea" helper="30 to 2000 characters, at least 3 words.">
        {(control) => <TextInput {...control} />}
      </Field>,
    );

    const input = screen.getByLabelText('Your idea');
    expect(input).toHaveAttribute('aria-describedby', 'idea-helper');
    expect(screen.getByText('30 to 2000 characters, at least 3 words.')).toHaveAttribute('id', 'idea-helper');
    expect(input).not.toHaveAttribute('aria-invalid');
  });

  it('replaces the helper with the error in the same place, so nothing moves', () => {
    render(
      <Field id="idea" label="Your idea" helper="30 to 2000 characters." error="Describe your idea in at least 30 characters.">
        {(control) => <TextInput {...control} />}
      </Field>,
    );

    const input = screen.getByLabelText('Your idea');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAttribute('aria-describedby', 'idea-error');
    expect(screen.getByText('Describe your idea in at least 30 characters.')).toBeInTheDocument();
    expect(screen.queryByText('30 to 2000 characters.')).not.toBeInTheDocument();
  });

  it('shows a character counter against the limit', () => {
    render(
      <Field id="idea" label="Your idea" counter={{ value: 312, max: 2000 }}>
        {(control) => <TextInput {...control} />}
      </Field>,
    );

    expect(screen.getByText('312 / 2000')).toBeInTheDocument();
  });
});
