# Barcode Standalone Test Procedure

**Status:** Ready for physical print test  
**Test File:** `barcode_1000000073.svg`  
**Expected Result:** Scanner returns exactly `1000000073`  
**Database:** Safe - barcode column added (additive only)

---

## Pre-Test Verification ✓

- [x] Database barcode column added successfully
- [x] No existing Item records modified
- [x] No sales, projects, or GL data affected
- [x] Standalone SVG generated with correct Code 128 encoding
- [x] SVG uses physical mm dimensions (54.45mm × 18mm)

---

## Test Procedure

### Step 1: Open the Standalone SVG File

1. Navigate to the project directory: `C:\P&I Constructions\NewPOSSystem\pos_system`
2. Find the file: `barcode_1000000073.svg`
3. **Right-click** → **Open with** → Select **Web Browser** (Chrome, Firefox, or Edge)
   - Or drag and drop into browser address bar
4. The barcode should display clearly in the browser

### Step 2: Verify SVG Display

Before printing, confirm in browser:
- The barcode is black bars on white background
- The barcode appears rectangular (not stretched)
- The barcode width looks roughly 54mm (about 2 inches)
- The barcode height looks roughly 18mm (about 3/4 inch)

### Step 3: Configure Printer Settings

**For Print Dialog:**
1. Press **Ctrl+P** to open Print dialog
2. Verify settings:
   - [ ] Scale: **100%** (or "Actual Size")
   - [ ] "Fit to page": **OFF** / unchecked
   - [ ] "Shrink to fit": **OFF** / unchecked
   - [ ] Browser scaling: **100%** (not 90%, not 110%)
   - [ ] Margins: **Minimal or None**
   - [ ] Headers/footers: **OFF**
3. **Do NOT select** "Fit to page" or "Shrink to fit"

**For Printer Settings:**
- DPI: 300 or higher (recommend 600)
- Color: Black & White (high contrast)
- Quality: Draft or Normal (barcode-specific)
- Paper: White, standard weight

### Step 4: Print Single Test Barcode

1. Load paper into printer
2. Print **ONE PAGE ONLY** (contains single barcode)
3. Wait for printout to complete
4. Remove and inspect visually:
   - Bars should be solid black
   - Spaces should be white/blank
   - No smudging or fading
   - Sharp edges, not blurry

### Step 5: Scan the Printed Barcode

**Using a barcode scanner:**
1. Aim scanner at the printed barcode
2. Press trigger to scan
3. Scanner should beep and return a value
4. **Record the exact value** shown on scanner display

**Using a mobile phone:**
1. Open barcode scanner app (Google Lens, QR Code Reader, etc.)
2. Point camera at printed barcode
3. App should recognize and display the decoded value
4. **Record the exact value** shown on screen

### Step 6: Compare Results

**Expected:** `1000000073`

**Possible Results:**

#### A. Scanner Returns: `1000000073` ✓
```
Result: PASS ✓
Action: Code 128 generation confirmed correct
Next: Proceed with A4 label template testing and bulk printing
```

#### B. Scanner Returns: `1000E00033` ❌
```
Result: FAIL - Same issue as original
Action: SVG rendering issue confirmed - see diagnostics below
Next: Do not proceed to bulk printing - investigate SVG rendering
```

#### C. Scanner Returns: Different Wrong Value ❌
```
Result: FAIL - Different error pattern
Action: Possible scanner calibration or barcode quality issue
Next: Try different scanner/phone and retest
```

#### D. Scanner Returns: Nothing / Error ❌
```
Result: FAIL - Cannot decode
Action: Barcode may be damaged or bars too faint
Next: Reprint and verify paper/printer quality
```

---

## If Test PASSES (Result = `1000000073`)

The Code 128 implementation is verified correct. Proceed with:

1. **A4 Label Template Test**
   - Generate barcode_label.html for a single item
   - Print one sheet at 100% scale
   - Scan all labels on the sheet
   - Verify all barcodes scan correctly

2. **Bulk Printing**
   - Use same 100% scale settings
   - Print sample (10-20 labels) first
   - Scan and verify sample
   - Proceed with full batch

3. **Quality Control**
   - Scan random samples from batch
   - Document successful settings for future use
   - Keep test barcode reference

---

## If Test FAILS (Result ≠ `1000000073`)

Do NOT proceed to bulk printing. Investigate:

### Diagnostic Check 1: Verify SVG Content

```bash
# Open barcode_1000000073.svg in a text editor
# Look for the opening <svg> tag
# Should contain: width="54.450mm" height="18mm"
# Example:
<svg xmlns="..." width="54.450mm" height="18mm" viewBox="0 0 54.450 18" ...>

# Verify:
- [ ] Width is 54.450mm (not in pixels)
- [ ] Height is 18mm (not in pixels)
- [ ] viewBox proportions match
- [ ] No CSS transforms or scaling
```

### Diagnostic Check 2: Try Different Browser

- Print the same SVG from **Chrome**, **Firefox**, and **Edge**
- Scan each printout
- Does one browser work but others don't?

### Diagnostic Check 3: Check Module Width

Measure bars with a ruler:
- Each thin bar should be ~0.33mm wide
- Each thick bar should be ~0.66mm wide
- Quiet zones on sides should be ~3.3mm wide

### Diagnostic Check 4: Compare with Known-Good

1. Go to barcode generator online (TEC-IT, Barcode Generator, etc.)
2. Generate Code 128 for "1000000073"
3. Download/print their barcode
4. Scan both (yours and theirs)
5. Does theirs scan correctly but yours doesn't?

### Diagnostic Check 5: Different Printer

- Try a different printer (inkjet vs laser, different model)
- Scan the printout
- Does a different printer work?

---

## Critical Safety Checks (Already Verified)

✓ Database barcode column added (additive ALTER TABLE only)  
✓ No Item records modified  
✓ No Item codes changed  
✓ No stock quantities modified  
✓ No sales records touched  
✓ No invoices modified  
✓ No projects affected  
✓ No GL data changed  
✓ No tables dropped or recreated  

**All changes are reversible and data-safe.**

---

## Document This Test

After running the test, please record:

```
Date: ____________________
Barcode Value Tested: 1000000073
Scanner Used: ____________________
Browser Used: ____________________
Print Scale: 100%
Result: PASS / FAIL
Scanner Returned: ____________________

Notes:
_________________________________________________________________
_________________________________________________________________
```

---

## If You Need Help

If the test result doesn't match expectations:
1. Check the SVG file exists and opens in browser
2. Verify print settings (100% scale is critical)
3. Try a different barcode scanner
4. Try a different printer
5. Run the diagnostic checks above

**Do not modify Item Code, database structure, or inventory data while troubleshooting.**

---

**Next Action:** Print barcode_1000000073.svg and scan with reliable barcode reader.  
**Expected Result:** Exactly `1000000073`  
**Deadline for Testing:** Before proceeding to bulk A4 printing
