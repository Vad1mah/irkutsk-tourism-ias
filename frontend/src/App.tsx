import { lazy, Suspense } from 'react'
import { Routes, Route, Link, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import { Sparkles } from 'lucide-react'

const Home = lazy(() => import('./pages/Home'))
const Chat = lazy(() => import('./pages/Chat'))
const Analytics = lazy(() => import('./pages/Analytics'))
const Events = lazy(() => import('./pages/Events'))
const Map = lazy(() => import('./pages/Map'))
const Forecast = lazy(() => import('./pages/Forecast'))
const About = lazy(() => import('./pages/About'))
const HotelDetail = lazy(() => import('./pages/HotelDetail'))

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[hsl(var(--primary))]"></div>
    </div>
  )
}

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-[hsl(var(--primary)/0.2)] to-[hsl(var(--accent)/0.2)] flex items-center justify-center mb-6">
        <Sparkles className="w-10 h-10 text-[hsl(var(--primary))]" />
      </div>
      <h1 className="text-4xl font-bold mb-2">404</h1>
      <p className="text-lg text-[hsl(var(--muted-foreground))] mb-6">Страница не найдена</p>
      <Link
        to="/"
        className="px-6 py-3 rounded-xl bg-gradient-to-r from-[hsl(var(--primary))] to-[hsl(var(--accent))] text-white font-medium hover:opacity-90 transition-opacity"
      >
        На главную
      </Link>
    </div>
  )
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route
          index
          element={
            <Suspense fallback={<LoadingSpinner />}>
              <Home />
            </Suspense>
          }
        />
        <Route
          path="chat"
          element={
            <Suspense fallback={<LoadingSpinner />}>
              <Chat />
            </Suspense>
          }
        />
        <Route
          path="analytics"
          element={
            <Suspense fallback={<LoadingSpinner />}>
              <Analytics />
            </Suspense>
          }
        />
        <Route path="situation" element={<Navigate to="/analytics" replace />} />
        <Route path="seasonality" element={<Navigate to="/forecast" replace />} />
        <Route path="dashboard" element={<Navigate to="/analytics" replace />} />
        <Route
          path="events"
          element={
            <Suspense fallback={<LoadingSpinner />}>
              <Events />
            </Suspense>
          }
        />
        <Route
          path="map"
          element={
            <Suspense fallback={<LoadingSpinner />}>
              <Map />
            </Suspense>
          }
        />
        <Route
          path="forecast"
          element={
            <Suspense fallback={<LoadingSpinner />}>
              <Forecast />
            </Suspense>
          }
        />
        <Route
          path="hotels/:id"
          element={
            <Suspense fallback={<LoadingSpinner />}>
              <HotelDetail />
            </Suspense>
          }
        />
        <Route
          path="about"
          element={
            <Suspense fallback={<LoadingSpinner />}>
              <About />
            </Suspense>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}

export default App
