package proxy

import (
	"errors"
	"proxy/config"
	str "strings"
	"time"
)

// MessageType is just that a type: request or reply
type MessageType uint

// ProbabilityDistribution is a type for probability distribution functions for rules
type ProbabilityDistribution uint

// 概率分布
const (
	ProbUniform = iota
	ProbExponential
	ProbNormal
)

// 概率分布 -> 名字
var distributionMap = map[ProbabilityDistribution]string{
	ProbUniform:     "uniform",
	ProbExponential: "exponential",
	ProbNormal:      "normal",
}

//消息类型 message channel type between client and server, via the proxy
const (
	MTypeUnknown MessageType = iota
	Request
	Response
	Publish
	Subscribe
)

//消息类型 -> 名字
var rMap = map[MessageType]string{
	MTypeUnknown: "unknown",
	Request:      "request",
	Response:     "response",
	Publish:      "publish",
	Subscribe:    "subscribe",
}

// Rule is a universal type for all rules.
type Rule struct {
	Enabled bool

	Source        string
	Dest          string
	MType         MessageType
	BodyPattern   string
	HeaderPattern string

	// First delay, then mangle and then abort
	DelayProbability  float64
	DelayDistribution ProbabilityDistribution
	DelayTime         time.Duration

	MangleProbability  float64
	MangleDistribution ProbabilityDistribution
	SearchString       string
	ReplaceString      string

	AbortProbability  float64
	AbortDistribution ProbabilityDistribution
	ErrorCode         int
}

// NopRule is a rule that does nothing. Useful default return value
var NopRule = Rule{Enabled: false}

// 分布名字 -> 编号
func getDistribution(distribution string) (ProbabilityDistribution, error) {
	switch str.ToLower(distribution) {
	case "uniform", "":
		return ProbUniform, nil
	case "exponential":
		return ProbExponential, nil
	case "normal":
		return ProbNormal, nil
	default:
		return ProbUniform, errors.New("unknown probability distribution")
	}
}

// 消息类型名字 -> 编号
func getMessageType(messageType string) (MessageType, error) {
	switch str.ToLower(messageType) {
	case "request":
		return Request, nil
	case "response":
		return Response, nil
	case "publish":
		return Publish, nil
	case "subscribe":
		return Subscribe, nil
	default:
		return MTypeUnknown, errors.New("unsupported request type")
	}
}

// NewRule return a new rule based on the config.
func NewRule(c config.RuleConfig) (r Rule, err error) {
	r = Rule{
		Enabled: true,
		Source:  c.Source,
		Dest:    c.Dest,
		//MType:              0,
		BodyPattern:      c.BodyPattern,
		HeaderPattern:    c.HeaderPattern,
		DelayProbability: c.DelayProbability,
		//DelayDistribution:  0,
		DelayTime:         time.Duration(0), // default
		MangleProbability: c.MangleProbability,
		//MangleDistribution: 0,
		SearchString:     c.SearchString,
		ReplaceString:    c.ReplaceString,
		AbortProbability: c.AbortProbability,
		//AbortDistribution:  0,
		ErrorCode: c.ErrorCode,
	}

	//sanity check
	//at least header or body pattern must be non-empty
	if r.HeaderPattern == "" {
		return NopRule, errors.New("HeaderPattern cannot be empty (specify * instead)")
	}
	if r.BodyPattern == "" {
		r.BodyPattern = "*"
	}

	// 至少有一种故障
	valid := r.DelayProbability > 0.0 || r.MangleProbability > 0.0 || r.AbortProbability > 0.0
	if !valid {
		return NopRule, errors.New("at least one of delay probability, mangle probability, abort probability must be non-zero and <=1.0")
	}

	// 设置消息类型
	if r.MType, err = getMessageType(c.MType); err != nil {
		return NopRule, err
	}

	r.DelayDistribution, err = getDistribution(c.DelayDistribution)
	if err != nil {
		return NopRule, err
	}
	if c.DelayTime != "" {
		r.DelayTime, err = time.ParseDuration(c.DelayTime)
		if err != nil {
			globallog.WithField("errmsg", err.Error()).Warn("Could not parse rule delay time")
			return NopRule, err
		}
	}

	r.MangleDistribution, err = getDistribution(c.MangleDistribution)
	if err != nil {
		return NopRule, err
	}

	r.AbortDistribution, err = getDistribution(c.AbortDistribution)
	if err != nil {
		return NopRule, err
	}

	return
}

// ToConfig 输出规则的可读版本 converts the rule into a human-readable string config.
func (r *Rule) ToConfig() config.RuleConfig {
	return config.RuleConfig{
		Source:        r.Source,
		Dest:          r.Dest,
		MType:         rMap[r.MType],
		BodyPattern:   r.BodyPattern,
		HeaderPattern: r.HeaderPattern,

		DelayProbability:  r.DelayProbability,
		DelayDistribution: distributionMap[r.DelayDistribution],
		DelayTime:         r.DelayTime.String(),

		MangleProbability:  r.MangleProbability,
		MangleDistribution: distributionMap[r.MangleDistribution],
		SearchString:       r.SearchString,
		ReplaceString:      r.ReplaceString,

		AbortProbability:  r.AbortProbability,
		AbortDistribution: distributionMap[r.AbortDistribution],
		ErrorCode:         r.ErrorCode,
	}
}
