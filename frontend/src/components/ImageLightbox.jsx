import { X } from 'lucide-react'

// عارض صورة مكبّرة (Lightbox). يُظهَر عند تمرير src، ويُغلق بالنقر أو زر الإغلاق.
export default function ImageLightbox({ src, onClose }) {
  if (!src) return null
  return (
    <div
      className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4 cursor-zoom-out"
      onClick={onClose}
    >
      <button
        onClick={onClose}
        className="absolute top-4 left-4 text-white/80 hover:text-white bg-white/10 rounded-full p-2"
        aria-label="إغلاق"
      >
        <X size={22} />
      </button>
      <img
        src={src}
        alt="معاينة"
        className="max-h-[90vh] max-w-[90vw] object-contain rounded-xl shadow-2xl"
        onClick={e => e.stopPropagation()}
      />
    </div>
  )
}
