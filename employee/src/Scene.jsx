import { useEffect, useRef } from 'react'
import * as THREE from 'three'

export default function Scene() {
  const mountRef = useRef(null)

  useEffect(() => {
    const mount = mountRef.current
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100)
    camera.position.set(0, 0, 7)
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    mount.appendChild(renderer.domElement)

    const group = new THREE.Group()
    const geometry = new THREE.IcosahedronGeometry(1.55, 1)
    const material = new THREE.MeshStandardMaterial({
      color: 0x4cf0c5,
      emissive: 0x0d4f5c,
      roughness: 0.22,
      metalness: 0.65,
      wireframe: true,
    })
    group.add(new THREE.Mesh(geometry, material))
    scene.add(group)
    scene.add(new THREE.AmbientLight(0x9be7ff, 1.8))
    const point = new THREE.PointLight(0x6c63ff, 8, 15)
    point.position.set(2, 2, 4)
    scene.add(point)

    const resize = () => {
      const width = mount.clientWidth
      const height = mount.clientHeight
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height, false)
    }
    resize()
    window.addEventListener('resize', resize)
    let frame
    const animate = () => {
      group.rotation.x += 0.002
      group.rotation.y += 0.006
      renderer.render(scene, camera)
      frame = requestAnimationFrame(animate)
    }
    animate()

    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', resize)
      geometry.dispose()
      material.dispose()
      renderer.dispose()
      mount.removeChild(renderer.domElement)
    }
  }, [])

  return <div className="scene" ref={mountRef} aria-hidden="true" />
}
