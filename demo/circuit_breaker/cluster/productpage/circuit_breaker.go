package main

import (
	"sync"
	"time"
)

type CircuitMode int

const (
	closed = CircuitMode(iota)
	halfOpen
	open
)

type CircuitBreaker struct {
	defaultValue string        // 默认值
	resetTime    time.Duration // 断开转半断开间隔
	mode         CircuitMode   //当前模式
	lock         *sync.Mutex

	// closed
	failures       int // 闭合时连续失败次数
	closedAttempts int // 闭合转断开门槛

	// halfOpen
	successes        int // 半断开连续成功次数
	halfOpenAttempts int // 半断开转闭合门槛

	// open
	openTime time.Time // 最后请求失败时间
}

func NewCircuitBreaker(defaultValue string, resetTime time.Duration,
	closedAttempts, halfOpenAttempts int) *CircuitBreaker {
	return &CircuitBreaker{
		defaultValue:     defaultValue,
		resetTime:        resetTime,
		mode:             closed,
		lock:             new(sync.Mutex),
		failures:         0,
		closedAttempts:   closedAttempts,
		successes:        0,
		halfOpenAttempts: halfOpenAttempts,
		openTime:         time.Time{},
	}
}

func (cb *CircuitBreaker) CheckIfRequest() bool {
	cb.lock.Lock()
	defer cb.lock.Unlock()

	switch cb.mode {
	case closed:
		return true
	case halfOpen:
		return true
	case open:
		if time.Now().After(cb.openTime.Add(cb.resetTime)) {
			// 断开一段时间，半断开
			cb.mode = halfOpen
			cb.successes = 0
			return true
		}
		return false
	}
	panic("CircuitBreaker mode error")
}

func (cb *CircuitBreaker) UpdateRequestStatus(ok bool) {
	cb.lock.Lock()
	defer cb.lock.Unlock()

	switch cb.mode {
	case closed:
		if ok {
			cb.failures = 0
		} else {
			cb.failures++
			if cb.failures > cb.closedAttempts {
				// 闭合连续失败，断开
				cb.mode = open
				cb.openTime = time.Now()
			}
		}
	case halfOpen:
		if ok {
			cb.successes++
			if cb.successes > cb.halfOpenAttempts {
				// 半断开连续成功，闭合
				cb.mode = closed
				cb.failures = 0
			}
		} else {
			// 半断开失败，重新断开
			cb.mode = open
			cb.openTime = time.Now()
		}
	case open:
		panic("CircuitBreaker open should not request")
	}
}

func (cb CircuitBreaker) GetDefaultValue() string {
	return cb.defaultValue
}
