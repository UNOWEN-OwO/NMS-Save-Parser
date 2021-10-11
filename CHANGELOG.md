# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Structured file operations
### Changed
- Decouple the main executable Python file

## [Experimental] (use with caution)
- Complete expedition mission
    - Use on an expedition save
    - Save then claim in game
- Change settlement Judgement
    - Jump next if not selecting any
- Fix timestamp error
    - Set timestamp that beyond current time to 2 hours back
    - Only set for certain key value
- Force fix timestamp error
    - Ignore filter

## [v1.0.0] - 11/10/2021
### Added
- Load/save compressed/uncompressed NMS save files.
- Fetch mappings from various sources and combine together.
- Parse the given save file as a JSON formatted file.
- Basic GUI by PyQt5.
- Verification on data entry
- Display timestamp & duration as readable/editable datetime
