/**
 * NeonTable: poker table component used across Home, Session, and any
 * other route that needs to show players + cards + pot.
 *
 * DOM/CSS is the stable primary renderer. Keep this shim so call sites
 * get one public component and table render errors stay isolated from
 * the rest of the page.
 */
import NeonTableDOM, { type NeonTableDOMProps, type PlayerSeatState } from "./NeonTableDOM";
import RenderBoundary from "./RenderBoundary";

// Public prop shape preserved for backwards-compat with existing call
// sites. The DOM implementation reads the same fields.
export type { PlayerSeatState };
export type NeonTableProps = NeonTableDOMProps;

export default function NeonTable(props: NeonTableProps) {
  return (
    <RenderBoundary>
      <NeonTableDOM {...props} />
    </RenderBoundary>
  );
}
