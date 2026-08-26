# Dependency Audit Method

## Inventory

Map direct and transitive dependencies by module and scope. Detect multiple versions, overrides, exclusions, peer constraints, platform packages, vendored code, and generated lockfiles. Treat the deployed artifact as the authoritative runtime surface when available.

## Vulnerabilities and Licenses

Correlate advisories with resolved versions and dependency paths. Evaluate whether the affected feature is reachable and whether configuration or environment changes exploitability. Record uncertainty when advisory databases disagree or are stale.

For licenses, separate declared metadata from included license text and actual distribution obligations. Escalate compatibility questions that need legal interpretation rather than presenting legal conclusions as engineering facts.

## Upgrade Planning

Group upgrades by shared constraints and test surface. Review release notes and migration guides for major or security-sensitive changes. Verify install/resolve, compile/build, focused behavior, integration, and packaging. Keep unrelated major upgrades out of an urgent vulnerability fix.
