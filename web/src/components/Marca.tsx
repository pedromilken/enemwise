/** Símbolo próprio do ENEMWise: três bolinhas de cartão-resposta subindo, o domínio que cresce. */
export function Marca({ size = 34 }: { size?: number }) {
  return (
    <svg className="marca-simbolo" width={size} height={size} viewBox="0 0 48 48" aria-hidden="true" focusable="false">
      <ellipse cx="12" cy="36" rx="11" ry="7" fill="none" stroke="currentColor" strokeWidth="3.5" opacity=".5" />
      <ellipse cx="24" cy="24" rx="11" ry="7" fill="currentColor" opacity=".5" />
      <ellipse cx="36" cy="12" rx="11" ry="7" fill="currentColor" />
    </svg>
  )
}
