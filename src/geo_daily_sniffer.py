#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
地球科学RSS监控系统 - 原版兼容
Original version compatibility wrapper for geo_daily_sniffer.py

This file maintains backward compatibility while providing access to enhanced features.
Users can still run the original filename but get the enhanced functionality.
"""

from geo_daily_sniffer_with_zone_scoring import main

if __name__ == "__main__":
    main()