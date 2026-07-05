from sqlalchemy.orm import Session

from ..models.metadata_change import AssetMetadataChangeEvent, AssetMetadataColumnSnapshot


class MetadataDiff:
    """Compare two column-level snapshots and generate change events."""

    @staticmethod
    def diff(
        db: Session,
        snapshot_id_from: int,
        snapshot_id_to: int,
        system_code: str | None = None,
        source_code: str | None = None,
    ) -> list[AssetMetadataChangeEvent]:
        old_filter = [AssetMetadataColumnSnapshot.snapshot_id == snapshot_id_from]
        new_filter = [AssetMetadataColumnSnapshot.snapshot_id == snapshot_id_to]
        if system_code:
            old_filter.append(AssetMetadataColumnSnapshot.system_code == system_code)
            new_filter.append(AssetMetadataColumnSnapshot.system_code == system_code)
        if source_code:
            old_filter.append(AssetMetadataColumnSnapshot.source_code == source_code)
            new_filter.append(AssetMetadataColumnSnapshot.source_code == source_code)

        old_rows = MetadataDiff._load_rows(db, old_filter)
        new_rows = MetadataDiff._load_rows(db, new_filter)

        events: list[AssetMetadataChangeEvent] = []

        old_tables = set(r["key"] for r in old_rows.values() if len(r["key"]) == 2)
        new_tables = set(r["key"] for r in new_rows.values() if len(r["key"]) == 2)

        def _sc_for_table(rows_dict, ns, tn):
            for row_key, row_val in rows_dict.items():
                if row_val["key"][:2] == (ns, tn):
                    return row_val.get("system_code", system_code or "")
            return system_code or ""

        for t in new_tables - old_tables:
            ns, tn = t
            sc = _sc_for_table(new_rows, ns, tn)
            events.append(MetadataDiff._event(
                snapshot_id_from, snapshot_id_to, sc, source_code or "",
                ns, tn, None, "table_added", severity="minor",
            ))

        for t in old_tables - new_tables:
            ns, tn = t
            sc = _sc_for_table(old_rows, ns, tn)
            events.append(MetadataDiff._event(
                snapshot_id_from, snapshot_id_to, sc, source_code or "",
                ns, tn, None, "table_removed", severity="high",
            ))

        all_col_keys = set(old_rows.keys()) | set(new_rows.keys())
        for key in all_col_keys:
            if len(key) != 3:
                continue
            ns, tn, cn = key
            sc = (new_rows.get(key, {}).get("system_code")
                  or old_rows.get(key, {}).get("system_code")
                  or system_code or "")
            if key in old_rows and key not in new_rows:
                old = old_rows[key]
                events.append(MetadataDiff._event(
                    snapshot_id_from, snapshot_id_to, sc, source_code or "",
                    ns, tn, cn, "column_removed", severity="high",
                    before_value=old["data"],
                ))
            elif key not in old_rows and key in new_rows:
                new = new_rows[key]
                events.append(MetadataDiff._event(
                    snapshot_id_from, snapshot_id_to, sc, source_code or "",
                    ns, tn, cn, "column_added", severity="medium",
                    after_value=new["data"],
                ))
            else:
                old = old_rows[key]
                new = new_rows[key]
                col_events = MetadataDiff._compare_column(
                    snapshot_id_from, snapshot_id_to, sc, source_code or "",
                    ns, tn, cn, old["data"], new["data"],
                )
                events.extend(col_events)

        return events

    @staticmethod
    def _load_rows(db: Session, filters: list) -> dict:
        from sqlalchemy import select as sa_select
        stmt = sa_select(AssetMetadataColumnSnapshot)
        for f in filters:
            stmt = stmt.where(f)
        rows = db.scalars(stmt).all()
        result = {}
        for r in rows:
            key = (r.namespace_name, r.table_name, r.column_name) if r.column_name else (r.namespace_name, r.table_name)
            result[key] = {
                "key": key,
                "data": {
                    "data_type": r.data_type, "length": r.length,
                    "nullable": r.nullable, "comment": r.comment,
                    "is_primary_key": r.is_primary_key,
                },
                "system_code": r.system_code or "",
            }
        return result

    @staticmethod
    def _compare_column(
        sid_from, sid_to, sc, src, ns, tn, cn, old_data, new_data,
    ) -> list[AssetMetadataChangeEvent]:
        events = []
        for field, sev in [("data_type", "high"), ("length", "medium"), ("nullable", "medium"), ("comment", "low")]:
            old_val = old_data.get(field)
            new_val = new_data.get(field)
            if str(old_val) != str(new_val):
                events.append(MetadataDiff._event(
                    sid_from, sid_to, sc, src, ns, tn, cn,
                    f"column_{field}_changed", severity=sev,
                    before_value={field: old_val}, after_value={field: new_val},
                ))
        return events

    @staticmethod
    def _event(sid_from, sid_to, sc, src, ns, tn, cn, change_type, severity, before_value=None, after_value=None):
        return AssetMetadataChangeEvent(
            snapshot_id_from=sid_from, snapshot_id_to=sid_to,
            system_code=sc, source_code=src,
            namespace_name=ns, table_name=tn, column_name=cn,
            change_type=change_type, severity=severity,
            before_value=before_value, after_value=after_value,
        )
