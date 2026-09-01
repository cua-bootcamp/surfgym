const UUID_STUB =
  'data:text/javascript,export const v4 = () => "test-uuid";';

export async function resolve(specifier, context, nextResolve) {
  if (specifier === 'uuid') {
    return { url: UUID_STUB, shortCircuit: true };
  }
  return nextResolve(specifier, context);
}
