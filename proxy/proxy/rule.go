package proxy

import (
	"errors"
	"proxy/config"
	"regexp"
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

	Source    string
	Dest      string
	MType     MessageType
	BodyReg   *regexp.Regexp
	HeaderReg *regexp.Regexp

	// First delay, then mangle and then abort
	DelayProbability  float64
	DelayDistribution ProbabilityDistribution
	DelayTime         time.Duration

	MangleProbability  float64
	MangleDistribution ProbabilityDistribution
	SearchReg          *regexp.Regexp
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
		//BodyReg:          nil,
		//HeaderReg:        nil,
		DelayProbability: c.DelayProbability,
		//DelayDistribution:  0,
		DelayTime:         time.Duration(0), // default
		MangleProbability: c.MangleProbability,
		//MangleDistribution: 0,
		//SearchReg: nil,
		ReplaceString:    c.ReplaceString,
		AbortProbability: c.AbortProbability,
		//AbortDistribution:  0,
		ErrorCode: c.ErrorCode,
	}

	// check regexp
	if r.HeaderReg, err = regexp.Compile(c.HeaderPattern); err != nil {
		return NopRule, errors.New("HeaderPattern error: " + err.Error())
	}
	if r.BodyReg, err = regexp.Compile(c.BodyPattern); err != nil {
		return NopRule, errors.New("BodyPattern error: " + err.Error())
	}

	// 至少有一种故障
	if r.DelayProbability == 0.0 && r.MangleProbability == 0.0 && r.AbortProbability == 0.0 {
		return NopRule, errors.New("at least one of delay probability, mangle probability and abort probability must be non-zero")
	}
	// 概率不相互独立，和小于1
	if r.DelayProbability == 0.0 && r.MangleProbability == 0.0 && r.AbortProbability == 0.0 {
		return NopRule, errors.New("the sum of delay probability, mangle probability and abort probability must be not more than one")
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
	if r.SearchReg, err = regexp.Compile(c.SearchString); err != nil {
		return NopRule, errors.New("SearchString error: " + err.Error())
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
		BodyPattern:   r.BodyReg.String(),
		HeaderPattern: r.HeaderReg.String(),

		DelayProbability:  r.DelayProbability,
		DelayDistribution: distributionMap[r.DelayDistribution],
		DelayTime:         r.DelayTime.String(),

		MangleProbability:  r.MangleProbability,
		MangleDistribution: distributionMap[r.MangleDistribution],
		SearchString:       r.SearchReg.String(),
		ReplaceString:      r.ReplaceString,

		AbortProbability:  r.AbortProbability,
		AbortDistribution: distributionMap[r.AbortDistribution],
		ErrorCode:         r.ErrorCode,
	}
}
