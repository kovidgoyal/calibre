#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

# Reading and writing the accessibility metadata of EPUB 3 books, see
# https://www.w3.org/TR/epub-a11y-11/ and https://www.w3.org/TR/epub-a11y-tech-11/

from calibre.ebooks.oeb.base import OPF
from calibre.ebooks.oeb.polish.container import Container

SUMMARY = 'schema:accessibilitySummary'
ACCESS_MODE = 'schema:accessMode'
ACCESS_MODE_SUFFICIENT = 'schema:accessModeSufficient'
FEATURE = 'schema:accessibilityFeature'
HAZARD = 'schema:accessibilityHazard'
CONFORMS_TO = 'dcterms:conformsTo'
CERTIFIED_BY = 'a11y:certifiedBy'
PROPERTIES = (SUMMARY, ACCESS_MODE, ACCESS_MODE_SUFFICIENT, FEATURE, HAZARD, CONFORMS_TO, CERTIFIED_BY)

# The values from the schema.org vocabularies that are useful for e-books
ACCESS_MODES = ('textual', 'visual', 'auditory', 'tactile', 'chartOnVisual', 'diagramOnVisual', 'mathOnVisual', 'textOnVisual', 'colorDependent')
SUFFICIENT_ACCESS_MODES = ('textual', 'visual', 'auditory', 'tactile', 'textual,visual', 'textual,auditory', 'auditory,visual')
FEATURES = (
    'alternativeText',
    'longDescription',
    'tableOfContents',
    'structuralNavigation',
    'readingOrder',
    'index',
    'pageNavigation',
    'pageBreakMarkers',
    'printPageNumbers',
    'displayTransformability',
    'ARIA',
    'MathML',
    'describedMath',
    'synchronizedAudioText',
    'ttsMarkup',
    'captions',
    'transcript',
    'annotations',
    'none',
)
CONFORMANCE = (
    'EPUB Accessibility 1.1 - WCAG 2.2 Level AA',
    'EPUB Accessibility 1.1 - WCAG 2.2 Level A',
    'EPUB Accessibility 1.1 - WCAG 2.1 Level AA',
    'EPUB Accessibility 1.1 - WCAG 2.1 Level A',
)

# Hazards are flashing, motion simulation and sound, each of which can be
# present, absent or unknown
HAZARDS = {
    'flashing': ('flashing', 'noFlashingHazard'),
    'motionSimulation': ('motionSimulation', 'noMotionSimulationHazard'),
    'sound': ('sound', 'noSoundHazard'),
}
PRESENT, ABSENT, UNKNOWN = 'present', 'absent', 'unknown'


def hazard_states(values: list[str]) -> dict[str, str]:
    ans = dict.fromkeys(HAZARDS, UNKNOWN)
    for val in values:
        if val == 'none':
            ans = dict.fromkeys(HAZARDS, ABSENT)
            break
        for hazard, (present, absent) in HAZARDS.items():
            if val == present:
                ans[hazard] = PRESENT
            elif val == absent:
                ans[hazard] = ABSENT
    return ans


def hazard_values(states: dict[str, str]) -> list[str]:
    if all(s == ABSENT for s in states.values()):
        return ['none']
    if all(s == UNKNOWN for s in states.values()):
        return ['unknown']
    ans = []
    for hazard, (present, absent) in HAZARDS.items():
        state = states.get(hazard, UNKNOWN)
        if state == PRESENT:
            ans.append(present)
        elif state == ABSENT:
            ans.append(absent)
    return ans


def metadata_parent(container: Container):
    return container.opf_xpath('//opf:metadata')[0]


def property_tags(container: Container, prop: str):
    # Only tags that describe the book itself, not other metadata
    return [m for m in container.opf_xpath('//opf:metadata/opf:meta[@property]') if m.get('property') == prop and not m.get('refines')]


def read_accessibility_metadata(container: Container) -> dict[str, list[str]]:
    ans = {}
    for prop in PROPERTIES:
        ans[prop] = [val for val in (' '.join((m.text or '').split()) for m in property_tags(container, prop)) if val]
    return ans


def set_accessibility_metadata(container: Container, metadata: dict[str, list[str]]) -> bool:
    """
    Replace the values of the accessibility properties in ``metadata``.
    Properties not in ``metadata`` are left unchanged. Returns True if the
    OPF was changed.
    """
    current = read_accessibility_metadata(container)
    changed = False
    parent = metadata_parent(container)
    for prop, values in metadata.items():
        values = [val for val in (' '.join(v.split()) for v in values) if val]
        if values == current.get(prop):
            continue
        for m in property_tags(container, prop):
            container.remove_from_xml(m)
        for val in values:
            m = parent.makeelement(OPF('meta'), property=prop)
            m.text = val
            container.insert_into_xml(parent, m)
        changed = True
    if changed:
        container.dirty(container.opf_name)
    return changed
