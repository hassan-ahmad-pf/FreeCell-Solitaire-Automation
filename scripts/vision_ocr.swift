// Print the text macOS Vision reads in an image, one line per observation:
// x0 <tab> y0 <tab> x1 <tab> y1 <tab> text   (pixels, origin top-left)
//
//     swiftc -O scripts/vision_ocr.swift -o log/bin/vision_ocr
//     log/bin/vision_ocr shot.png
import AppKit
import Foundation
import Vision

guard CommandLine.arguments.count > 1,
      let image = NSImage(contentsOfFile: CommandLine.arguments[1]),
      let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("usage: vision_ocr IMAGE\n".data(using: .utf8)!)
    exit(2)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
do {
    try VNImageRequestHandler(cgImage: cg, options: [:]).perform([request])
} catch {
    FileHandle.standardError.write("vision_ocr: \(error)\n".data(using: .utf8)!)
    exit(1)
}

let w = Double(cg.width), h = Double(cg.height)
for observation in request.results ?? [] {
    guard let text = observation.topCandidates(1).first?.string else { continue }
    let b = observation.boundingBox
    print("\(Int(b.minX * w))\t\(Int((1 - b.maxY) * h))\t\(Int(b.maxX * w))\t\(Int((1 - b.minY) * h))\t\(text)")
}
